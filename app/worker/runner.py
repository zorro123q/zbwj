import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from flask import current_app

from app.extensions import db
from app.models import File, Job
from app.services.prompt_registry import PromptRegistry
from app.worker.components.excel_exporter import ExcelExporter
from app.worker.components.parser import Parser
from app.worker.components.extractor import Extractor
from domain.templates.registry import TemplateRegistry
from domain.exports.word import export_by_template, WordExportError
# 【关键新增】引入相似度计算引擎
from domain.similarity.engine import SimilarityEngine


class InProcessRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._threads: Dict[str, threading.Thread] = {}

    def start(self, job_id: str) -> None:
        job_id = (job_id or "").strip()
        if not job_id:
            return

        app = current_app._get_current_object()

        with self._lock:
            t = self._threads.get(job_id)
            if t is not None and t.is_alive():
                return

            t = threading.Thread(target=self._run, args=(app, job_id), daemon=True)
            self._threads[job_id] = t
            t.start()

    def _set_job(
            self,
            job_id: str,
            *,
            status: Optional[str] = None,
            stage: Optional[str] = None,
            progress: Optional[int] = None,
            artifact_json_path: Optional[str] = None,
            artifact_xlsx_path: Optional[str] = None,
            artifact_docx_path: Optional[str] = None,
            error_message: Optional[str] = None,
    ) -> None:
        job = db.session.get(Job, job_id)
        if job is None:
            raise RuntimeError("job not found")

        if status is not None:
            job.status = status
        if stage is not None:
            job.stage = stage
        if progress is not None:
            p = int(progress)
            if p < 0:
                p = 0
            if p > 100:
                p = 100
            job.progress = p
        if artifact_json_path is not None:
            job.artifact_json_path = artifact_json_path
        if artifact_xlsx_path is not None:
            job.artifact_xlsx_path = artifact_xlsx_path
        if artifact_docx_path is not None:
            job.artifact_docx_path = artifact_docx_path
        if error_message is not None:
            job.error_message = error_message

        db.session.commit()

    def _repo_root(self) -> Path:
        return Path(current_app.root_path).parent

    def _abs_path_from_rel(self, rel_path: str) -> Path:
        rel_path = (rel_path or "").replace("\\", "/")
        return self._repo_root() / Path(rel_path)

    def _load_script(self, script_id: str) -> Dict[str, Any]:
        scripts = PromptRegistry.load_all()
        for s in scripts:
            if s.get("script_id") == script_id:
                return s
        raise RuntimeError(f"script not found: {script_id}")

    def _fake_llm_output(self, text: str, job_id: str, script: Dict[str, Any]) -> Dict[str, Any]:
        data = Extractor.extract(text)
        data["job_id"] = job_id
        data["script"] = {"script_id": script.get("script_id"), "version": script.get("version")}
        if script.get("template_id") and script.get("template_version"):
            data["template"] = {
                "template_id": script.get("template_id"),
                "version": script.get("template_version"),
            }
        return data

    def _validate_result_json(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("result must be an object")
        tables = data.get("tables")
        if not isinstance(tables, list) or len(tables) == 0:
            raise ValueError("result.tables must be a non-empty array")

    def _run(self, app, job_id: str) -> None:
        with app.app_context():
            current_stage = "PENDING"
            current_progress = 0

            def advance(stage: str, progress: int, status: Optional[str] = None):
                nonlocal current_stage, current_progress
                current_stage = stage
                current_progress = int(progress)
                self._set_job(job_id, stage=stage, progress=progress, status=status)

            try:
                advance("VALIDATE", 5, status="RUNNING")
                time.sleep(0.05)

                job = db.session.get(Job, job_id)
                if job is None:
                    raise RuntimeError("job not found")

                # =================================================================
                # 【新功能分支】 文档相似性检测 (Similarity Check)
                # =================================================================
                if job.script_id == "DOC_SIMILARITY_CHECK":
                    advance("PARSING_FILES", 10, status="RUNNING")

                    # 逻辑约定：file_id 是源文件，model_id 借用存储目标文件ID
                    source_file_id = job.file_id
                    target_file_id = job.model_id

                    f_src = db.session.get(File, source_file_id)
                    f_tgt = db.session.get(File, target_file_id)

                    if not f_src or not f_tgt:
                        raise ValueError("One of the files is missing")

                    # 解析两个文件
                    src_path = self._abs_path_from_rel(f_src.storage_path)
                    tgt_path = self._abs_path_from_rel(f_tgt.storage_path)

                    # 调用 Parser 解析文本
                    text_a = Parser.parse(src_path, f_src.ext)
                    text_b = Parser.parse(tgt_path, f_tgt.ext)

                    advance("CALCULATING_VECTORS", 40, status="RUNNING")

                    # 调用相似度引擎
                    engine = SimilarityEngine()
                    report = engine.compare_documents(text_a, text_b)

                    advance("SAVING_RESULT", 90, status="RUNNING")

                    # 保存结果 JSON
                    artifacts_dir = f"{current_app.config.get('ARTIFACT_STORAGE_DIR', 'storage/artifacts')}/{job_id}"
                    artifacts_dir = artifacts_dir.replace("\\", "/")
                    json_rel = f"{artifacts_dir}/similarity_report.json"
                    json_abs = self._abs_path_from_rel(json_rel)

                    json_abs.parent.mkdir(parents=True, exist_ok=True)

                    with json_abs.open("w", encoding="utf-8") as fp:
                        json.dump(report, fp, ensure_ascii=False, indent=2)

                    self._set_job(
                        job_id,
                        status="SUCCEEDED",
                        stage="DONE",
                        progress=100,
                        artifact_json_path=json_rel,
                        error_message=None,
                    )
                    return
                # =================================================================

                # 常规任务逻辑
                f = db.session.get(File, job.file_id)
                if f is None:
                    raise RuntimeError("file not found")

                if job.script_id == "EXPORT_TEMPLATE_DOCX":
                    advance("EXPORT_DOCX", 40, status="RUNNING")
                    template_version = (job.model_id or "").strip()
                    try:
                        result = export_by_template(
                            job_id=job_id,
                            template_id="tender_reuse",
                            version=template_version,
                            company_id=None,
                        )
                    except WordExportError as exc:
                        raise RuntimeError(str(exc)) from exc

                    self._set_job(
                        job_id,
                        status="SUCCEEDED",
                        stage="DONE",
                        progress=100,
                        artifact_docx_path=result.get("docx_path"),
                        error_message=None,
                    )
                    return

                script = self._load_script(job.script_id)
                template_id = script.get("template_id")
                template_version = script.get("template_version")
                if template_id and template_version:
                    TemplateRegistry.get(template_id, template_version)

                ext = (f.ext or "").lower().strip()
                if ext not in ("txt", "docx"):
                    raise ValueError("only txt/docx are supported")

                src_path = self._abs_path_from_rel(f.storage_path)
                if not src_path.exists() or not src_path.is_file():
                    raise FileNotFoundError("source file missing on disk")

                advance("PARSE", 20)
                text = Parser.parse(src_path, ext)

                advance("BUILD_PROMPT", 35)
                advance("LLM_CALL", 60)
                result = self._fake_llm_output(text, job_id, script)

                advance("VALIDATE_JSON", 80)
                self._validate_result_json(result)

                advance("EXPORT_EXCEL", 95)
                artifacts_dir = f"{current_app.config.get('ARTIFACT_STORAGE_DIR', 'storage/artifacts')}/{job_id}"
                artifacts_dir = artifacts_dir.replace("\\", "/")
                json_rel = f"{artifacts_dir}/result.json"
                xlsx_rel = f"{artifacts_dir}/result.xlsx"
                json_abs = self._abs_path_from_rel(json_rel)
                xlsx_abs = self._abs_path_from_rel(xlsx_rel)
                json_abs.parent.mkdir(parents=True, exist_ok=True)

                with json_abs.open("w", encoding="utf-8") as fp:
                    json.dump(result, fp, ensure_ascii=False, indent=2)

                ExcelExporter.export(result, xlsx_abs)

                self._set_job(
                    job_id,
                    status="SUCCEEDED",
                    stage="DONE",
                    progress=100,
                    artifact_json_path=json_rel,
                    artifact_xlsx_path=xlsx_rel,
                    error_message=None,
                )

            except Exception as e:
                msg = str(e) if str(e) else e.__class__.__name__
                try:
                    self._set_job(
                        job_id,
                        status="FAILED",
                        stage=current_stage,
                        progress=current_progress,
                        error_message=msg,
                    )
                except Exception:
                    pass


runner = InProcessRunner()