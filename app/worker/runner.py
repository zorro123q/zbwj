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

STAGE_PROGRESS = [
    ("VALIDATE", 5),
    ("PARSE", 20),
    ("BUILD_PROMPT", 35),
    ("LLM_CALL", 60),
    ("VALIDATE_JSON", 80),
    ("EXPORT_EXCEL", 95),
    ("DONE", 100),
]


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
        raise RuntimeError("script not found")

    def _fake_llm_output(self, text: str, job_id: str, script: Dict[str, Any]) -> Dict[str, Any]:
        # 这里不接真实 LLM，直接规则抽取
        data = Extractor.extract(text)
        # 补充一点元信息（可选）
        data["job_id"] = job_id
        data["script"] = {"script_id": script.get("script_id"), "version": script.get("version")}
        return data

    def _validate_result_json(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("result must be an object")

        tables = data.get("tables")
        if not isinstance(tables, list) or len(tables) == 0:
            raise ValueError("result.tables must be a non-empty array")

        for i, t in enumerate(tables):
            if not isinstance(t, dict):
                raise ValueError(f"tables[{i}] must be an object")
            if not isinstance(t.get("sheet_name"), str) or not t["sheet_name"].strip():
                raise ValueError(f"tables[{i}].sheet_name must be a non-empty string")
            cols = t.get("columns")
            rows = t.get("rows")
            if not isinstance(cols, list) or len(cols) == 0 or not all(isinstance(c, str) for c in cols):
                raise ValueError(f"tables[{i}].columns must be a non-empty string array")
            if not isinstance(rows, list):
                raise ValueError(f"tables[{i}].rows must be an array")
            for rj, r in enumerate(rows):
                if not isinstance(r, list):
                    raise ValueError(f"tables[{i}].rows[{rj}] must be an array")

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
                # VALIDATE 5
                advance("VALIDATE", 5, status="RUNNING")
                time.sleep(0.05)

                job = db.session.get(Job, job_id)
                if job is None:
                    raise RuntimeError("job not found")

                f = db.session.get(File, job.file_id)
                if f is None:
                    raise RuntimeError("file not found")

                script = self._load_script(job.script_id)

                ext = (f.ext or "").lower().strip()
                if ext not in ("txt", "docx"):
                    raise ValueError("only txt/docx are supported")

                src_path = self._abs_path_from_rel(f.storage_path)
                if not src_path.exists() or not src_path.is_file():
                    raise FileNotFoundError("source file missing on disk")

                # PARSE 20
                advance("PARSE", 20)
                time.sleep(0.05)
                text = Parser.parse(src_path, ext)

                # BUILD_PROMPT 35
                advance("BUILD_PROMPT", 35)
                time.sleep(0.05)

                # LLM_CALL 60
                advance("LLM_CALL", 60)
                time.sleep(0.15)
                result = self._fake_llm_output(text, job_id, script)

                # VALIDATE_JSON 80
                advance("VALIDATE_JSON", 80)
                time.sleep(0.05)
                self._validate_result_json(result)

                # EXPORT_EXCEL 95
                advance("EXPORT_EXCEL", 95)
                time.sleep(0.05)

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

                # DONE 100
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
                    # 保留最后一个 stage/progress，便于你看到卡在哪个阶段
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
