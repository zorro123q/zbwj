import os
import unittest
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.seed import seed_document_types
from app.models import Company, DocumentType, Evidence, Person, StoredFile


class IndexSearchAPITestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"

        self.app = create_app("testing")
        self.app.config["TESTING"] = True

        with self.app.app_context():
            db.create_all()
            seed_document_types()

            # owners
            p = Person(id="p1", name="张三")
            c = Company(id="c1", name="某公司")
            db.session.add_all([p, c])
            db.session.commit()

            dt_idfront = (
                db.session.query(DocumentType)
                .filter(DocumentType.scope == "PERSON", DocumentType.code == "idcard_front")
                .first()
            )
            dt_bl = (
                db.session.query(DocumentType)
                .filter(DocumentType.scope == "COMPANY", DocumentType.code == "business_license")
                .first()
            )

            # stored files (no need real disk files for search)
            sf1 = StoredFile(
                id="f1",
                original_name="idfront.jpg",
                ext="jpg",
                mime_type="image/jpeg",
                size_bytes=10,
                sha256="a" * 64,
                storage_rel_path="storage/certs/person/p1/idcard_front/f1.jpg",
            )
            sf2 = StoredFile(
                id="f2",
                original_name="bl.png",
                ext="png",
                mime_type="image/png",
                size_bytes=20,
                sha256="b" * 64,
                storage_rel_path="storage/certs/company/c1/business_license/f2.png",
            )
            sf3 = StoredFile(
                id="f3",
                original_name="expired.png",
                ext="png",
                mime_type="image/png",
                size_bytes=20,
                sha256="c" * 64,
                storage_rel_path="storage/certs/company/c1/business_license/f3.png",
            )
            db.session.add_all([sf1, sf2, sf3])
            db.session.commit()

            now = datetime.utcnow()

            ev_person = Evidence(
                id="e1",
                scope="PERSON",
                owner_id="p1",
                document_type_id=dt_idfront.id,
                file_id="f1",
                cert_no="ID123",
                issuer="公安局",
                issued_at=now - timedelta(days=10),
                expires_at=now + timedelta(days=365),
                status="VALID",
                tags="身份证正面,张三",
            )

            ev_company = Evidence(
                id="e2",
                scope="COMPANY",
                owner_id="c1",
                document_type_id=dt_bl.id,
                file_id="f2",
                cert_no="BL-001",
                issuer="市场监管局",
                issued_at=now - timedelta(days=200),
                expires_at=None,
                status="VALID",
                tags="营业执照,某公司",
            )

            ev_company_expired = Evidence(
                id="e3",
                scope="COMPANY",
                owner_id="c1",
                document_type_id=dt_bl.id,
                file_id="f3",
                cert_no="BL-OLD",
                issuer="市场监管局",
                issued_at=now - timedelta(days=1000),
                expires_at=now - timedelta(days=1),
                status="EXPIRED",
                tags="营业执照,过期",
            )

            db.session.add_all([ev_person, ev_company, ev_company_expired])
            db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def test_q_company_business_license(self):
        r = self.client.get("/api/v1/index/search?q=营业执照")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["total"] >= 1)
        scopes = {it["scope"] for it in data["items"]}
        self.assertIn("COMPANY", scopes)

    def test_q_person_idcard_front(self):
        r = self.client.get("/api/v1/index/search?q=身份证正面")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["total"] >= 1)
        scopes = {it["scope"] for it in data["items"]}
        self.assertIn("PERSON", scopes)

    def test_scope_filter(self):
        r = self.client.get("/api/v1/index/search?scope=PERSON")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["scope"], "PERSON")

    def test_pagination(self):
        r1 = self.client.get("/api/v1/index/search?page=1&page_size=1&sort=created_at_desc")
        self.assertEqual(r1.status_code, 200)
        d1 = r1.get_json()
        self.assertEqual(d1["page_size"], 1)
        self.assertEqual(len(d1["items"]), 1)
        self.assertTrue(d1["total"] >= 2)

        r2 = self.client.get("/api/v1/index/search?page=2&page_size=1&sort=created_at_desc")
        self.assertEqual(r2.status_code, 200)
        d2 = r2.get_json()
        self.assertEqual(d2["page"], 2)
        self.assertEqual(len(d2["items"]), 1)

    def test_valid_on_filters_expired(self):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        r = self.client.get(f"/api/v1/index/search?q=营业执照&valid_on={today}")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        # should not contain expired evidence e3
        ids = {it["evidence_id"] for it in data["items"]}
        self.assertNotIn("e3", ids)


if __name__ == "__main__":
    unittest.main()
