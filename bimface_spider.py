import requests
import base64

APP_KEY = "HB35SuUr16CKDSdwCFIO5O8FqorB8kDg"
APP_SECRET = "HnxoLayhiOgXzSlo7bg42ej9bizr1Wku"
FILE_ID = "10000990421273"

def get_access_token(app_key, app_secret):
    url = "https://api.bimface.com/oauth2/token"
    credential = f"{app_key}:{app_secret}"
    headers = {"Authorization": f"Basic {base64.b64encode(credential.encode('utf-8')).decode('utf-8')}"}
    return requests.post(url, headers=headers, proxies={"http": None, "https": None}).json()['data']['token']

def analyze_and_sort_elements(token, file_id):
    print("📡 启动大数据特征提取器：正在抓取全量坐标并按面积排序...\n")
    
    url_ids = f"https://api.bimface.com/data/v2/files/{file_id}/elementIds"
    headers = {"Authorization": f"Bearer {token}"}
    
    id_list = requests.get(url_ids, headers=headers, proxies={"http": None, "https": None}).json().get('data', [])
    
    valid_elements = []
    
    # 为了速度，我们随机抽 100 个探测，通常足够覆盖那几个大体量构件了
    print("🔨 正在砸盲盒提取尺寸 (可能需要 10-20 秒，请耐心等待)...")
    for eid in id_list[:100]: 
        url_detail = f"https://api.bimface.com/data/v2/files/{file_id}/elements/{eid}"
        res = requests.get(url_detail, headers=headers, proxies={"http": None, "https": None})
        if res.status_code == 200:
            bbox = res.json().get('data', {}).get('boundingBox')
            if bbox:
                l = bbox['max']['x'] - bbox['min']['x']
                w = bbox['max']['y'] - bbox['min']['y']
                area = l * w
                cx = (bbox['min']['x'] + bbox['max']['x']) / 2.0
                cy = (bbox['min']['y'] + bbox['max']['y']) / 2.0
                
                valid_elements.append({
                    "id": eid, "area": area, "length": l, "width": w, "cx": cx, "cy": cy
                })
                
                if len(valid_elements) >= 10: # 收集到 10 个有体积的就停手
                    break

    # 核心：按面积从大到小排序！
    sorted_elements = sorted(valid_elements, key=lambda x: x['area'], reverse=True)
    
    print("\n📊 物理构件特征分析报告 (按占地面积降序)：")
    print("-" * 75)
    for idx, el in enumerate(sorted_elements):
        # 教授的智能推测逻辑
        guess = "未知"
        if idx == 0: guess = "可能是【场地边界/道路】(面积最大)"
        elif el['length'] / el['width'] > 0.8 and el['length'] / el['width'] < 1.2 and el['area'] < 50:
            guess = "可能是【塔吊底座】(长宽接近1:1，且面积较小)"
        elif idx == 1 or idx == 2:
            guess = "可能是【主体建筑】"
            
        print(f"[{idx+1}] ID: {el['id']:<15} | 面积: {el['area']:<7.1f} ㎡ | 尺寸: {el['length']:.1f} x {el['width']:.1f} | 💡 预测: {guess}")
    print("-" * 75)
    print("\n👉 现在，你可以直接把这些 ID 填入 data_gateway.py 的 ROLE_MAP 字典中了！")

if __name__ == "__main__":
    token = get_access_token(APP_KEY, APP_SECRET)
    if token:
        analyze_and_sort_elements(token, FILE_ID)