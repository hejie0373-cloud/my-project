"""
初始化数据：插入角色等种子数据
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

# 初始角色数据
INITIAL_ROLES = [
    ("super_admin", "超级管理员 — 管理所有店铺和平台配置"),
    ("store_owner", "店主 — 管理自己的店铺、员工和数据"),
    ("staff", "店员 — 管理客户和到店记录，不可查看营收数据"),
    ("partner", "渠道合作方 — 查看合作店铺的聚合统计数据"),
    ("association", "行业协会 — 查看行业聚合统计数据"),
]

# 初始套餐数据
INITIAL_PLANS = [
    ("basic", 500, "基础版 — 适合初创小店"),
    ("professional", 2000, "专业版 — 适合成长型店铺"),
    ("enterprise", 10000, "旗舰版 — 适合连锁店铺"),
]


async def init_db(connection: AsyncConnection):
    """
    初始化种子数据
    使用 INSERT IGNORE 防止重复执行报错
    """
    # 1. 插入角色
    for name, description in INITIAL_ROLES:
        await connection.execute(
            text(
                "INSERT IGNORE INTO roles (id, name, description, created_at, updated_at) "
                "VALUES (REPLACE(UUID(), '-', ''), :name, :description, NOW(), NOW())"
            ),
            {"name": name, "description": description},
        )
    logger.info("种子数据：角色初始化完成 (%d 条)", len(INITIAL_ROLES))
