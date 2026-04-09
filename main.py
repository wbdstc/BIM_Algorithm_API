from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import random
import math

app = FastAPI(title="BIM 智能场布优化引擎")

# ==========================================
# 1. 升级版 API 数据接收模型
# ==========================================
class SiteBoundary(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float

class WorkingCrane(BaseModel):
    name: str
    x: float
    y: float

class Obstacle(BaseModel):
    name: str
    x: float
    y: float
    length: float
    width: float

class MaterialBox(BaseModel):
    length: float
    width: float
    height: float

class Material(BaseModel):
    id: str
    name: str
    weight_tons: float
    bounding_box: MaterialBox

class LayoutRequest(BaseModel):
    # 删除了旧的 project_id，完全拥抱新数据结构
    site_boundary: SiteBoundary
    working_cranes: List[WorkingCrane]
    obstacles: List[Obstacle]
    materials_to_place: List[Material]

# ==========================================
# 2. 核心算法工具函数
# ==========================================
def calculate_distance(x1, y1, x2, y2):
    """计算两点之间的欧氏距离"""
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def check_collision(x, y, l, w, obstacles):
    """AABB 包围盒碰撞检测：如果在任何障碍物内部，返回 True"""
    for obs in obstacles:
        # 判断两个矩形是否重叠
        if not (x + l/2 < obs.x - obs.length/2 or 
                x - l/2 > obs.x + obs.length/2 or 
                y + w/2 < obs.y - obs.width/2 or 
                y - w/2 > obs.y + obs.width/2):
            return True # 发生碰撞！
    return False

# ==========================================
# 3. 优化引擎 API 接口
# ==========================================
@app.post("/optimize_layout")
def optimize_layout(request: LayoutRequest):
    print("\n🚀 [智能寻优引擎] 接收到新任务，开始解析场地数据...")
    print(f"📍 场地边界: X({request.site_boundary.min_x:.1f} ~ {request.site_boundary.max_x:.1f}), Y({request.site_boundary.min_y:.1f} ~ {request.site_boundary.max_y:.1f})")
    print(f"🏗️ 激活塔吊数量: {len(request.working_cranes)}")
    print(f"🧱 识别到障碍物: {len(request.obstacles)} 个")
    
    results = []

    # 遍历需要布置的每一个材料堆场
    for material in request.materials_to_place:
        print(f"\n⚙️ 正在为【{material.name}】寻找最佳放置点...")
        
        best_x, best_y = 0.0, 0.0
        min_cost = float('inf')
        assigned_crane = "无"
        
        # 启发式随机搜索 (简化版遗传算法思想，撒点 5000 次寻找最优解)
        # 实际毕设中你可以把这里的逻辑替换为更复杂的标准遗传算法
        for _ in range(5000):
            # 1. 在绝对边界内随机生成基因（坐标）
            test_x = random.uniform(request.site_boundary.min_x, request.site_boundary.max_x)
            test_y = random.uniform(request.site_boundary.min_y, request.site_boundary.max_y)
            
            # 2. 碰撞检测（防穿模）
            if check_collision(test_x, test_y, material.bounding_box.length, material.bounding_box.width, request.obstacles):
                continue # 撞墙了，放弃这个点
                
            # 3. 适应度评估（计算到最近塔吊的搬运成本）
            current_min_dist = float('inf')
            nearest_crane = ""
            for crane in request.working_cranes:
                dist = calculate_distance(test_x, test_y, crane.x, crane.y)
                if dist < current_min_dist:
                    current_min_dist = dist
                    nearest_crane = crane.name
            
            # 综合成本 = 距离 * 物料重量 (距离越短，重量越轻，成本越低)
            cost = current_min_dist * material.weight_tons
            
            # 4. 择优保留
            if cost < min_cost:
                min_cost = cost
                best_x = test_x
                best_y = test_y
                assigned_crane = nearest_crane
        
        # 保存该材料的最优结果
        if min_cost == float('inf'):
            status = "❌ 失败：场地太挤，找不到合适位置"
        else:
            status = "✅ 寻优成功"
            
        results.append({
            "material_name": material.name,
            "status": status,
            "optimal_x": round(best_x, 2),
            "optimal_y": round(best_y, 2),
            "nearest_crane": assigned_crane,
            "transport_cost_score": round(min_cost, 2)
        })
        print(f"   {status} -> 坐标: ({best_x:.2f}, {best_y:.2f}) | 归属: {assigned_crane}")

    return {
        "message": "场布优化计算完成",
        "layouts": results
    }