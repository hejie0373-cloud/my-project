"""
数据分析 Pydantic Schema
"""
from datetime import date, datetime
from typing import Optional, List, Literal

from pydantic import BaseModel


# ============================================================
# 仪表盘
# ============================================================

class DashboardStat(BaseModel):
    """统计卡片"""
    label: str
    value: int | float
    unit: str = ""
    change_pct: Optional[float] = None  # 环比变化
    icon: str = ""


class VisitTrendPoint(BaseModel):
    """到店趋势数据点"""
    date: str
    count: int


class TopCustomer(BaseModel):
    """高风险客户"""
    id: str
    name: str
    phone: str
    churn_score: float


class DashboardData(BaseModel):
    """仪表盘聚合数据"""
    total_customers: int
    high_risk_count: int
    high_value_count: int
    today_visits: int
    visit_trend: List[VisitTrendPoint]
    top_risk_customers: List[TopCustomer]
    churn_distribution: dict  # {"high": n, "medium": n, "low": n}


# ============================================================
# 报表
# ============================================================

class VisitReportItem(BaseModel):
    """到店报表项"""
    period: str
    visit_count: int
    unique_customers: int


class RevenueReportItem(BaseModel):
    """营收报表项"""
    period: str
    total_amount: float
    avg_amount: float
    payment_distribution: dict = {}


class AiReportData(BaseModel):
    """AI 指标报表"""
    high_risk_count: int
    churn_score_distribution: dict  # {"0-20": n, "20-40": n, ...}
    clv_avg: float
    copy_adoption_rate: float
    total_customers_scored: int


class ReportRequest(BaseModel):
    """报表查询参数"""
    type: Literal["visits", "revenue", "ai"]
    start_date: date
    end_date: date
    granularity: Literal["day", "week", "month"] = "day"
