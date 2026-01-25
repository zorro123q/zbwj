import os
import sys
import uuid
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

DEFAULT_COMPANY_ROOT = r"C:\Users\Administrator\Desktop\W\kxjl\test\data\公司"
DEFAULT_PERSON_ROOT = r"C:\Users\Administrator\Desktop\W\kxjl\test\data\人员信息"

# 公司：公司根目录/证书中文名/*.jpg
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

# 人员：支持两种结构
# A) 人员信息/张三/身份证正面/*.jpg  （原逻辑）
PERSON_FOLDER_MAP = {
    "身份证正面": "idcard_front",
    "身份证反面": "idcard_back",
    "毕业证": "diploma",
    "硕士证书":"master_degree",
    "博士证书":"Doctor_degree",

    "初级人工智能应用师": "ai_app_junior",
    "高级人工智能应用师": "Hjai_app_junior",
    "高级Python技术开发师": "python_dev_senior",
    "智能客服开发师": "cs_dev",

    "中级信息系统项目管理师": "Z_Information_Manager",
    "高级信息系统项目管理师": "H_Information_Manager",

    "中级软件设计师": "ZSoftware",
    "高级软件设计师": "HSoftware",

    "中级网络工程师": "ZInternet",
    "高级网络工程师": "HInternet",

    "计算机三级证书": "Level3_Computer",
    "计算机四级证书": "Level4_Computer",

    "中级系统架构设计师": "Z_Systems_Designer",
    "高级系统架构设计师": "H_Systems_Designer",
}

# B) 人员信息/张三/*.jpg  （新增：从文件名猜 doc_type_code）
# 关键词命中顺序：从更具体到更泛
PERSON_FILENAME_RULES = [
    (["身份证正面", "身份证-正面", "idcard_front", "front"], "idcard_front"),
    (["身份证反面", "身份证-反面", "idcard_back", "back"], "idcard_back"),
    (["毕业证", "diploma"], "diploma"),
    (["硕士证书", "master_degree"], "master_degree"),
    (["博士证书", "Doctor_degree"], "Doctor_degree"),
    (["初级人工智能应用师", "初级人工智能", "ai_app_junior"], "ai_app_junior"),
    (["高级人工智能应用师", "高级人工智能", "Hjai_app_junior"], "Hjai_app_junior"),

    (["高级Python技术开发师", "高级python", "python_dev_senior"], "python_dev_senior"),
    (["智能客服开发师", "智能客服", "cs_dev"], "cs_dev"),

    (["中级信息系统项目管理师", "Z_Information_Manager"], "Z_Information_Manager"),
    (["高级信息系统项目管理师", "H_Information_Manager"], "H_Information_Manager"),

    (["中级软件设计师", "ZSoftware"], "ZSoftware"),
    (["高级软件设计师", "HSoftware"], "HSoftware"),

    (["中级网络工程师", "ZInternet"], "ZInternet"),
    (["高级网络工程师", "HInternet"], "HInternet"),

    (["计算机三级证书", "Level3_Computer"], "Level3_Computer"),
    (["计算机四级证书", "Level4_Computer"], "Level4_Computer"),

    (["中级系统架构设计师", "Z_Systems_Designer"], "Z_Systems_Designer"),
    (["高级系统架构设计师", "H_Systems_Designer"], "H_Systems_Designer"),
]

PERSON_DEFAULT_DOC_TYPE_CODE = "cs_dev"  # ✅ 文件名猜不到时用这个兜底


def iter_images(folder: Path):
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            yield p


def get_or_create_company(name: str) -> str:
    name = (name or "").strip() or "demo_company"
    row = db.session.query(Company).filter(Company.name == name).first()
    if row:
        return row.id
    cid = str(uuid.uuid4())
    db.session.add(Company(id=cid, name=name))
    db.session.commit()
    return cid


def get_or_create_person(person_name: str) -> str:
    person_name = (person_name or "").strip()
    if not person_name:
        raise ValueError("empty person name")
    row = db.session.query(Person).filter(Person.name == person_name).first()
    if row:
        return row.id
    pid = str(uuid.uuid4())
    db.session.add(Person(id=pid, name=person_name))
    db.session.commit()
    return pid


def detect_person_doc_type_from_filename(filename: str) -> str:
    name = (filename or "").lower()
    for keywords, code in PERSON_FILENAME_RULES:
        for kw in keywords:
            if kw.lower() in name:
                return code
    return PERSON_DEFAULT_DOC_TYPE_CODE


def import_company(company_root: Path, company_name: str = "demo_company"):
    if not company_root.exists():
        print(f"[SKIP] company_root not exists: {company_root}")
        return

    company_id = get_or_create_company(company_name)
    total = ok = dup = fail = 0

    for sub in company_root.iterdir():
        if not sub.is_dir():
            continue
        folder_cn = sub.name
        doc_code = COMPANY_FOLDER_MAP.get(folder_cn)
        if not doc_code:
            print(f"[SKIP] 未映射的公司证书文件夹: {folder_cn}")
            continue

        for img_path in iter_images(sub):
            total += 1
            try:
                mt = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                with open(img_path, "rb") as f:
                    fs = FileStorage(stream=f, filename=img_path.name, content_type=mt)
                    res = save_image(fs, scope="COMPANY", owner_id=company_id, doc_type_code=doc_code, tags=folder_cn)

                if res.get("dedup"):
                    dup += 1
                    print(f"[DUP] COMPANY {folder_cn} {img_path.name}")
                else:
                    ok += 1
                    print(f"[OK]  COMPANY {folder_cn} {img_path.name} -> {res['storage_rel_path']} (orig={res.get('original_name')})")
            except Exception as e:
                fail += 1
                db.session.rollback()
                print(f"[FAIL] {img_path} -> {e}")

    print(f"[DONE] COMPANY total={total} ok={ok} dup={dup} fail={fail} company_id={company_id}")


def import_person(person_root: Path):
    """
    支持两种结构：
      A) 人员信息/人名/证书类型/*.jpg  -> 用 PERSON_FOLDER_MAP
      B) 人员信息/人名/*.jpg         -> 从文件名关键词猜 doc_type_code
    """
    if not person_root.exists():
        print(f"[SKIP] person_root not exists: {person_root}")
        return

    total = ok = dup = fail = 0

    for person_dir in person_root.iterdir():
        if not person_dir.is_dir():
            continue

        person_name = person_dir.name
        try:
            person_id = get_or_create_person(person_name)
        except Exception as e:
            db.session.rollback()
            print(f"[FAIL] create person {person_name} -> {e}")
            continue

        # --- 情况 B：人名目录下直接有图片 ---
        direct_imgs = [p for p in person_dir.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]
        if direct_imgs:
            for img_path in direct_imgs:
                total += 1
                try:
                    doc_code = detect_person_doc_type_from_filename(img_path.name)
                    mt = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                    with open(img_path, "rb") as f:
                        fs = FileStorage(stream=f, filename=img_path.name, content_type=mt)
                        res = save_image(
                            fs,
                            scope="PERSON",
                            owner_id=person_id,
                            doc_type_code=doc_code,
                            tags=f"{person_name},by_filename",
                        )

                    if res.get("dedup"):
                        dup += 1
                        print(f"[DUP] PERSON {person_name} {img_path.name} -> {doc_code}")
                    else:
                        ok += 1
                        print(f"[OK]  PERSON {person_name} {img_path.name} -> {doc_code} -> {res['storage_rel_path']} (orig={res.get('original_name')})")
                except Exception as e:
                    fail += 1
                    db.session.rollback()
                    print(f"[FAIL] {img_path} -> {e}")

        # --- 情况 A：人名目录下还有证书类型子目录 ---
        for doc_dir in person_dir.iterdir():
            if not doc_dir.is_dir():
                continue
            folder_cn = doc_dir.name
            doc_code = PERSON_FOLDER_MAP.get(folder_cn)
            if not doc_code:
                print(f"[SKIP] 未映射的人员证书文件夹: {person_name}/{folder_cn}")
                continue

            for img_path in iter_images(doc_dir):
                total += 1
                try:
                    mt = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                    with open(img_path, "rb") as f:
                        fs = FileStorage(stream=f, filename=img_path.name, content_type=mt)
                        res = save_image(
                            fs,
                            scope="PERSON",
                            owner_id=person_id,
                            doc_type_code=doc_code,
                            tags=f"{person_name},{folder_cn}",
                        )

                    if res.get("dedup"):
                        dup += 1
                        print(f"[DUP] PERSON {person_name}/{folder_cn} {img_path.name}")
                    else:
                        ok += 1
                        print(f"[OK]  PERSON {person_name}/{folder_cn} {img_path.name} -> {res['storage_rel_path']} (orig={res.get('original_name')})")
                except Exception as e:
                    fail += 1
                    db.session.rollback()
                    print(f"[FAIL] {img_path} -> {e}")

    print(f"[DONE] PERSON total={total} ok={ok} dup={dup} fail={fail}")


def main():
    company_root = Path(os.getenv("IMPORT_COMPANY_ROOT", DEFAULT_COMPANY_ROOT))
    person_root = Path(os.getenv("IMPORT_PERSON_ROOT", DEFAULT_PERSON_ROOT))
    company_name = os.getenv("IMPORT_COMPANY_NAME", "demo_company")

    env = os.getenv("FLASK_ENV", "development")
    app = create_app(env)

    with app.app_context():
        seed_document_types()

        print(f"Company root: {company_root}")
        print(f"Person  root: {person_root}")
        print(f"Company name: {company_name}")

        import_company(company_root, company_name=company_name)
        import_person(person_root)


if __name__ == "__main__":
    main()
