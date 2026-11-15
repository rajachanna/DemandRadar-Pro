from demandradar.storage import Store
from demandradar.sources import Candidate


def test_ingest_and_summary(cfg,sample):
    db=Store(cfg.db_path)
    r=db.ingest([sample])
    assert r=={"fetched":1,"new":1,"duplicates":0}
    assert db.summary()["total"]==1


def test_idempotent_repeated_source(cfg,sample):
    db=Store(cfg.db_path)
    db.ingest([sample]); assert db.ingest([sample])["new"]==0
    assert db.summary()["total"]==1


def test_idempotent_same_url_different_source(cfg,sample):
    db=Store(cfg.db_path)
    db.ingest([sample])
    alt=Candidate("github_issues","another",sample.url,"Different title","Different details",sample.published_at)
    assert db.ingest([alt])["new"]==0
    assert db.summary()["total"]==1


def test_preserves_manual_status_on_rescan(cfg,sample):
    db=Store(cfg.db_path)
    db.ingest([sample]);record=db.list()[0]
    db.update_status(record["id"],"shortlisted","Verified requirement")
    db.ingest([sample])
    stored=db.list()[0]
    assert stored["status"]=="shortlisted" and stored["note"]=="Verified requirement"


def test_list_filter_and_search(cfg,sample):
    db=Store(cfg.db_path)
    db.ingest([sample])
    assert len(db.list(query="FastAPI"))==1
    assert len(db.list(query="nonexistent"))==0
    assert len(db.list(status="shortlisted"))==0
    item=db.list()[0]
    db.update_status(item["id"],"shortlisted","")
    assert len(db.list(status="shortlisted"))==1
    assert len(db.list(min_score=100))<=1


def test_missing_update_returns_none(cfg):
    assert Store(cfg.db_path).update_status(100,"new","") is None
    assert Store(cfg.db_path).get(999) is None


def test_log_scans(cfg):
    db=Store(cfg.db_path);db.log_scan("github","python_contracts",5,3,"success")
    assert db.scans()[0]["new_count"]==3
    assert db.scans()[0]["source"]=="github"


def test_scan_detail_limits(cfg):
    db=Store(cfg.db_path);db.log_scan("github","ai_workflows",0,0,"failed","x"*600)
    assert len(db.scans()[0]["detail"])==500


def test_empty_pipeline(cfg):
    s=Store(cfg.db_path).summary()
    assert (s["total"],s["won"],s["contacted"])==(0,0,0)


def test_long_note_in_storage(cfg,sample):
    db=Store(cfg.db_path);db.ingest([sample]);id=db.list()[0]["id"]
    db.update_status(id,"won","Human verified")
    assert db.summary()["won"]==1
