#!/bin/bash
set -e

echo "🚀 客留 生产环境部署脚本"
echo "========================="

# 拉取/构建镜像
echo "📦 构建镜像..."
docker compose -f docker-compose.prod.yml build

# 启动服务
echo "▶️  启动服务..."
docker compose -f docker-compose.prod.yml up -d

# 等待数据库就绪
echo "⏳ 等待 MySQL 就绪..."
sleep 15

# 运行数据库迁移
echo "🗄️  运行数据库迁移..."
docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

# 提示
echo ""
echo "========================="
echo "✅ 部署完成！"
echo "   访问: http://localhost"
echo ""
echo "常用命令："
echo "   查看日志: docker compose -f docker-compose.prod.yml logs -f"
echo "   停止服务: docker compose -f docker-compose.prod.yml down"
