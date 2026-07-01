from PIL import Image, ImageDraw, ImageFont
import os

def create_poster():
    # 创建画布
    width, height = 800, 1200
    img = Image.new('RGB', (width, height), color=(26, 26, 46))
    draw = ImageDraw.Draw(img)
    
    # 渐变色函数
    def gradient_color(y, height, color1, color2):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        return (r, g, b)
    
    # 绘制渐变背景
    for y in range(height):
        color = gradient_color(y, height, (26, 26, 46), (15, 52, 96))
        draw.line([(0, y), (width, y)], fill=color)
    
    # 尝试加载字体
    try:
        font_title = ImageFont.truetype("msyh.ttc", 48)
        font_large = ImageFont.truetype("msyh.ttc", 36)
        font_medium = ImageFont.truetype("msyh.ttc", 24)
        font_small = ImageFont.truetype("msyh.ttc", 18)
        font_tiny = ImageFont.truetype("msyh.ttc", 16)
    except:
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
    
    # 主标题
    draw.text((width//2, 80), "电梯仿真系统", fill=(255, 255, 255), font=font_title, anchor="mm")
    draw.text((width//2, 140), "基于SimPy的智能电梯调度优化系统", fill=(200, 200, 200), font=font_medium, anchor="mm")
    
    # 分隔线
    draw.rectangle([50, 180, 750, 185], fill=(102, 126, 234))
    
    # 核心特性
    features = [
        ("🎯", "智能调度算法", "SCAN算法优化 + 多因素评分机制"),
        ("📊", "分组策略对比", "奇偶分组 vs 长链结构 vs 不分组"),
        ("⚡", "效率提升显著", "等待时间-40% · 吞吐量+35%"),
        ("🔬", "数学理论支撑", "排队论 + 柔性制造理论")
    ]
    
    y_pos = 220
    for emoji, title, desc in features:
        # 特性卡片
        draw.rounded_rectangle([40, y_pos, 760, y_pos + 90], radius=15, fill=(40, 40, 70))
        draw.text((70, y_pos + 20), emoji, fill=(255, 255, 255), font=font_large)
        draw.text((140, y_pos + 15), title, fill=(255, 255, 255), font=font_medium)
        draw.text((140, y_pos + 55), desc, fill=(150, 150, 150), font=font_small)
        y_pos += 110
    
    # 统计数据
    draw.rectangle([40, y_pos + 20, 760, y_pos + 140], fill=(50, 50, 80))
    stats = [("15+", "实验次数"), ("2089", "代码行数"), ("40%", "效率提升"), ("17", "仿真楼层")]
    x_pos = 100
    for value, label in stats:
        draw.text((x_pos, y_pos + 50), value, fill=(102, 126, 234), font=font_large)
        draw.text((x_pos, y_pos + 95), label, fill=(150, 150, 150), font=font_tiny)
        x_pos += 180
    
    # 优化亮点
    y_pos = y_pos + 180
    draw.rounded_rectangle([40, y_pos, 760, y_pos + 200], radius=15, fill=(30, 40, 80))
    draw.text((width//2, y_pos + 25), "✨ 核心优化特性", fill=(255, 255, 255), font=font_medium, anchor="mm")
    
    highlights = [
        "✓ 任务仓库统一管理机制",
        "✓ 智能多因素分配器",
        "✓ 双电梯协作机制",
        "✓ ETA到达时间预测",
        "✓ 批量停靠优化",
        "✓ 实时动画可视化",
        "✓ 微信小程序监控",
        "✓ 楼层显示屏支持"
    ]
    
    y_offset = y_pos + 60
    x_offset = 80
    for i, text in enumerate(highlights):
        col = i % 2
        row = i // 2
        draw.text((x_offset + col * 350, y_offset + row * 30), text, fill=(180, 180, 180), font=font_small)
    
    # 底部信息
    y_pos = y_pos + 240
    draw.rectangle([40, y_pos, 760, y_pos + 3], fill=(102, 126, 234))
    draw.text((width//2, y_pos + 40), "开源项目 · 欢迎参与", fill=(255, 255, 255), font=font_medium, anchor="mm")
    draw.text((width//2, y_pos + 80), "github.com/quarktong/Elevator_simulation", fill=(102, 126, 234), font=font_small, anchor="mm")
    draw.text((width//2, y_pos + 115), "基于SimPy事件驱动仿真框架 · Python 3.x", fill=(120, 120, 120), font=font_tiny, anchor="mm")
    
    # 保存图片
    img.save('项目宣传海报.png', 'PNG', quality=95)
    print("海报已生成: 项目宣传海报.png")

if __name__ == "__main__":
    create_poster()
