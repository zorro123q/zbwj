import os
import sys
import uuid
import re
from datetime import datetime
from pathlib import Path
import mimetypes

# ✅ 确保可以 import app
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from werkzeug.datastructures import FileStorage

from app import create_app
from app.extensions import db
from app.seed import seed_document_types
from app.models import Person, Company
from app.services.cert_storage import save_image

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

DEFAULT_COMPANY_ROOT = r"C:\Users\Administrator\Desktop\ZBRJ\V4 - 副本\data\公司"
DEFAULT_PERSON_ROOT = r"C:\Users\Administrator\Desktop\ZBRJ\V4 - 副本\data\人员信息"

COMPANY_FOLDER_MAP = {
    "营业执照": "business_license",
    "ISO体系认证证书": "iso_certificate",
    "高新技术企业认证证书": "high_tech_enterprise",
    "开户许可证": "bank_account_permit",
    "软件著作权": "software_copyright",
    "专利证书": "patent",
    "资质类证书": "qualification_cert",
    "增值电信业务经营许可证": "value_added_telecom_license",
    "第三方测试报告": "third_party_test_report",
    "软件产品证书": "software_product_cert",
    "荣誉证书": "honor_cert",
}

PERSON_FOLDER_MAP = {
    "身份证正面": "idcard_front", "身份证反面": "idcard_back", "毕业证": "diploma",
    "硕士证书": "master_degree", "博士证书": "Doctor_degree",
    "初级人工智能应用师": "ai_app_junior", "高级人工智能应用师": "Hjai_app_junior",
    "高级Python技术开发师": "python_dev_senior", "智能客服开发师": "cs_dev",
    "中级信息系统项目管理师": "Z_Information_Manager", "高级信息系统项目管理师": "H_Information_Manager",
    "中级软件设计师": "ZSoftware", "高级软件设计师": "HSoftware",
    "中级网络工程师": "ZInternet", "高级网络工程师": "HInternet",
    "计算机三级证书": "Level3_Computer", "计算机四级证书": "Level4_Computer",
    "中级系统架构设计师": "Z_Systems_Designer", "高级系统架构设计师": "H_Systems_Designer",
}

PERSON_FILENAME_RULES = [
    (["身份证正面", "front"], "idcard_front"), (["身份证反面", "back"], "idcard_back"),
    (["毕业证", "diploma"], "diploma"), (["硕士证书", "master_degree"], "master_degree"),
    (["博士证书", "Doctor_degree"], "Doctor_degree"),
    (["初级人工智能"], "ai_app_junior"), (["高级人工智能"], "Hjai_app_junior"),
    (["高级Python"], "python_dev_senior"), (["智能客服"], "cs_dev"),
    (["中级信息系统项目管理师"], "Z_Information_Manager"), (["高级信息系统项目管理师"], "H_Information_Manager"),
    (["中级软件设计师"], "ZSoftware"), (["高级软件设计师"], "HSoftware"),
    (["中级网络工程师"], "ZInternet"), (["高级网络工程师"], "HInternet"),
    (["计算机三级证书"], "Level3_Computer"), (["计算机四级证书"], "Level4_Computer"),
    (["中级系统架构设计师"], "Z_Systems_Designer"), (["高级系统架构设计师"], "H_Systems_Designer"),
]
PERSON_DEFAULT_DOC_TYPE_CODE = "cs_dev"


def extract_expire_date(filename: str):
    """超级强大的日期提取器，支持多种常见的日期格式"""
    # 1. 匹配 YYYY-MM-DD (例如 2026-05-20)
    match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', filename)
    if match: return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    # 2. 匹配 YYYY.MM.DD (例如 2026.05.20)
    match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', filename)
    if match: return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    # 3. 匹配 YYYY年MM月DD日 (例如 2026年05月20日)
    match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]?', filename)
    if match: return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    # 4. 匹配紧凑型 YYYYMMDD (例如 20260520) - 限制年份为 20xx 或 19xx
    match = re.search(r'((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])', filename)
    if match: return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    return None


def iter_images(folder: Path):
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS: yield p


def get_or_create_company(name: str):
    name = (name or "").strip() or "demo_company"
    row = db.session.query(Company).filter(Company.name == name).first()
    if row: return row.id
    cid = str(uuid.uuid4())
    db.session.add(Company(id=cid, name=name))
    db.session.commit()
    return cid


def get_or_create_person(person_name: str):
    person_name = (person_name or "").strip()
    row = db.session.query(Person).filter(Person.name == person_name).first()
    if row: return row.id
    pid = str(uuid.uuid4())
    db.session.add(Person(id=pid, name=person_name))
    db.session.commit()
    return pid


def detect_person_doc_type_from_filename(filename: str):
    name = (filename or "").lower()
    for keywords, code in PERSON_FILENAME_RULES:
        for kw in keywords:
            if kw.lower() in name: return code
    return PERSON_DEFAULT_DOC_TYPE_CODE


def import_company(company_root: Path, company_name: str = "demo_company"):
    if not company_root.exists(): return
    company_id = get_or_create_company(company_name)
    total = ok = dup = fail = 0

    for sub in company_root.iterdir():
        if not sub.is_dir(): continue
        folder_cn = sub.name
        doc_code = COMPANY_FOLDER_MAP.get(folder_cn)
        if not doc_code: continue

        for img_path in iter_images(sub):
            total += 1
            try:
                # 🚀 核心逻辑：提取到期日期
                expire_date = extract_expire_date(img_path.name)
                mt = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                with open(img_path, "rb") as f:
                    fs = FileStorage(stream=f, filename=img_path.name, content_type=mt)
                    res = save_image(
                        fs, scope="COMPANY", owner_id=company_id,
                        doc_type_code=doc_code, tags=folder_cn,
                        expires_at=expire_date  # 🚀 传入到期时间
                    )
                if res.get("dedup"):
                    dup += 1
                else:
                    ok += 1
                    print(
                        f"[OK] 公司证书: {img_path.name} | 到期日识别: {expire_date.strftime('%Y-%m-%d') if expire_date else '无'}")
            except Exception as e:
                fail += 1
                db.session.rollback()

    print(f"[DONE] COMPANY total={total} ok={ok} dup={dup} fail={fail}")


def import_person(person_root: Path):
    if not person_root.exists(): return
    total = ok = dup = fail = 0

    for person_dir in person_root.iterdir():
        if not person_dir.is_dir(): continue
        person_name = person_dir.name
        try:
            person_id = get_or_create_person(person_name)
        except Exception:
            db.session.rollback();
            continue

        direct_imgs = [p for p in person_dir.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]
        if direct_imgs:
            for img_path in direct_imgs:
                total += 1
                try:
                    doc_code = detect_person_doc_type_from_filename(img_path.name)
                    # 🚀 核心逻辑：提取到期日期
                    expire_date = extract_expire_date(img_path.name)
                    mt = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                    with open(img_path, "rb") as f:
                        fs = FileStorage(stream=f, filename=img_path.name, content_type=mt)
                        res = save_image(
                            fs, scope="PERSON", owner_id=person_id, doc_type_code=doc_code,
                            tags=f"{person_name},by_filename",
                            expires_at=expire_date  # 🚀 传入到期时间
                        )
                    if res.get("dedup"):
                        dup += 1
                    else:
                        ok += 1
                        print(
                            f"[OK] 人员证书: {img_path.name} | 到期日识别: {expire_date.strftime('%Y-%m-%d') if expire_date else '无'}")
                except Exception as e:
                    fail += 1
                    db.session.rollback()

        for doc_dir in person_dir.iterdir():
            if not doc_dir.is_dir(): continue
            folder_cn = doc_dir.name
            doc_code = PERSON_FOLDER_MAP.get(folder_cn)
            if not doc_code: continue

            for img_path in iter_images(doc_dir):
                total += 1
                try:
                    # 🚀 核心逻辑：提取到期日期
                    expire_date = extract_expire_date(img_path.name)
                    mt = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                    with open(img_path, "rb") as f:
                        fs = FileStorage(stream=f, filename=img_path.name, content_type=mt)
                        res = save_image(
                            fs, scope="PERSON", owner_id=person_id, doc_type_code=doc_code,
                            tags=f"{person_name},{folder_cn}",
                            expires_at=expire_date  # 🚀 传入到期时间
                        )
                    if res.get("dedup"):
                        dup += 1
                    else:
                        ok += 1
                        print(
                            f"[OK] 人员证书: {img_path.name} | 到期日识别: {expire_date.strftime('%Y-%m-%d') if expire_date else '无'}")
                except Exception as e:
                    fail += 1
                    db.session.rollback()

    print(f"[DONE] PERSON total={total} ok={ok} dup={dup} fail={fail}")


def main():
    company_root = Path(os.getenv("IMPORT_COMPANY_ROOT", DEFAULT_COMPANY_ROOT))
    person_root = Path(os.getenv("IMPORT_PERSON_ROOT", DEFAULT_PERSON_ROOT))
    company_name = os.getenv("IMPORT_COMPANY_NAME", "demo_company")

    env = os.getenv("FLASK_ENV", "development")
    app = create_app(env)

    with app.app_context():
        seed_document_types()
        import_company(company_root, company_name=company_name)
        import_person(person_root)


if __name__ == "__main__":
    main()