import pytest


@pytest.fixture
def kaggle_csv() -> bytes:
    return b"date,store,item,sales\n2013-01-01,1,2,10\n2013-01-02,1,2,0\n"
