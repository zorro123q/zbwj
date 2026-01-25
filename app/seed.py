from app.extensions import db
from app.models import DocumentType


def seed_document_types():
    items = [
        # PERSON
        ("PERSON", "idcard_front", "身份证正面", "ID"),
        ("PERSON", "idcard_back", "身份证反面", "ID"),
        ("PERSON", "diploma", "毕业证", "EDU"),
        ("PERSON", "master_degree", "硕士证书", "EDU"),
        ("PERSON", "Doctor_degree", "博士证书", "EDU"),
        ("PERSON", "ai_app_junior", "初级人工智能应用师", "CERT"),
        ("PERSON", "python_dev_senior", "高级Python技术开发师", "CERT"),
        ("PERSON", "cs_dev", "智能客服开发师", "CERT"),
        ("PERSON","Z_Information_Manager","中级信息系统项目管理师","CERT"),
        ("PERSON", "H_Information_Manager", "高级信息系统项目管理师", "CERT"),
        ("PERSON", "Hjai_app_junior", "高级人工智能应用师", "CERT"),
        ("PERSON", "ZSoftware", "中级软件设计师", "CERT"),
        ("PERSON", "HSoftware", "高级软件设计师", "CERT"),
        ("PERSON", "ZInternet", "中级网络工程师", "CERT"),
        ("PERSON", "HInternet", "高级网络工程师", "CERT"),
        ("PERSON", "Level3_Computer", "计算机三级证书", "CERT"),
        ("PERSON", "Level4_Computer", "计算机四级证书", "CERT"),
        ("PERSON", "Z_Systems_Designer", "中级系统架构设计师", "CERT"),
        ("PERSON", "H_Systems_Designer", "高级系统架构设计师", "CERT"),


        # COMPANY
        ("COMPANY", "business_license", "营业执照", "LICENSE"),
        ("COMPANY", "iso_certificate", "ISO体系认证证书", "CERT"),
        ("COMPANY", "high_tech_enterprise", "高新技术企业认证证书", "CERT"),
        ("COMPANY", "bank_account_permit", "开户许可证", "LICENSE"),
        ("COMPANY", "software_copyright", "软件著作权", "CERT"),
        ("COMPANY", "patent", "专利证书", "CERT"),
        ("COMPANY", "qualification_cert", "资质类证书", "CERT"),
        ("COMPANY", "value_added_telecom_license", "增值电信业务经营许可证", "LICENSE"),
        ("COMPANY", "third_party_test_report", "第三方测试报告", "REPORT"),
        ("COMPANY", "software_product_cert", "软件产品证书", "CERT"),
        ("COMPANY", "honor_cert", "荣誉证书", "HONOR"),
    ]

    for scope, code, name, category in items:
        exists = (
            db.session.query(DocumentType)
            .filter(DocumentType.scope == scope, DocumentType.code == code)
            .first()
        )
        if not exists:
            db.session.add(DocumentType(scope=scope, code=code, name=name, category=category))

    db.session.commit()
