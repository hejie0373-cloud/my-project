"""
Elasticsearch 客户端封装
- 客户索引创建/同步/搜索
- ES 不可用时优雅降级（返回空结果，不崩溃）
"""
import logging
from typing import List, Optional

from elasticsearch import Elasticsearch

from app.core.config import settings

logger = logging.getLogger(__name__)

CUSTOMER_INDEX = "keliudb_customers"

# 索引 Mapping
CUSTOMER_MAPPING = {
    "mappings": {
        "properties": {
            "name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "phone": {"type": "keyword"},
            "store_id": {"type": "keyword"},
            "is_deleted": {"type": "boolean"},
        }
    }
}

# 全局 ES 客户端（懒初始化）
_es_client: Optional[Elasticsearch] = None
_es_available: bool = True


def get_es_client() -> Optional[Elasticsearch]:
    """
    获取 ES 客户端（懒加载 + 自动创建索引）
    返回 None 表示 ES 不可用
    """
    global _es_client, _es_available

    if not _es_available:
        return None

    if _es_client is not None:
        return _es_client

    try:
        _es_client = Elasticsearch(
            [settings.ES_URL],
            request_timeout=2,
            max_retries=0,
            retry_on_timeout=False,
        )
        # 检查连接
        if not _es_client.ping():
            logger.warning("ES ping 失败，搜索功能将降级")
            _es_available = False
            _es_client = None
            return None

        # 自动创建索引
        if not _es_client.indices.exists(index=CUSTOMER_INDEX):
            _es_client.indices.create(index=CUSTOMER_INDEX, body=CUSTOMER_MAPPING)
            logger.info(f"ES 索引已创建: {CUSTOMER_INDEX}")

        logger.info("ES 客户端初始化成功")
        return _es_client

    except Exception as e:
        logger.warning(f"ES 不可用: {e}，搜索功能降级为 MySQL LIKE")
        _es_available = False
        _es_client = None
        return None


def sync_customer_to_es(customer_id: str, name: str, phone: str, store_id: str) -> None:
    """同步客户到 ES（创建或更新）"""
    es = get_es_client()
    if es is None:
        return

    try:
        doc = {
            "name": name,
            "phone": phone,
            "store_id": store_id,
            "is_deleted": False,
        }
        es.index(index=CUSTOMER_INDEX, id=customer_id, document=doc, refresh=False)
        logger.debug(f"ES 已索引: customer_id={customer_id}")
    except Exception as e:
        logger.error(f"ES 索引失败: {e}")


def delete_customer_from_es(customer_id: str) -> None:
    """从 ES 删除客户文档"""
    es = get_es_client()
    if es is None:
        return

    try:
        es.delete(index=CUSTOMER_INDEX, id=customer_id, ignore=[404])
        logger.debug(f"ES 已删除: customer_id={customer_id}")
    except Exception as e:
        logger.error(f"ES 删除失败: {e}")


def search_customers_in_es(store_id: str, query: str, size: int = 20) -> List[str]:
    """
    在 ES 中搜索客户，返回匹配的 customer_id 列表

    - 对 name 和 phone 做 multi_match
    - 过滤 store_id
    - 返回 _id 列表（按相关度排序）
    """
    es = get_es_client()
    if es is None:
        return []

    try:
        body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["name", "phone"],
                                "type": "best_fields",
                            }
                        },
                        {"term": {"store_id": store_id}},
                        {"term": {"is_deleted": False}},
                    ]
                }
            },
            "_source": False,
            "size": size,
        }
        response = es.search(index=CUSTOMER_INDEX, body=body)
        hits = response.get("hits", {}).get("hits", [])
        return [hit["_id"] for hit in hits]

    except Exception as e:
        logger.error(f"ES 搜索失败: {e}")
        return []
