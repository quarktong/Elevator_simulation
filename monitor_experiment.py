import os
import time
from datetime import datetime

def check_progress():
    """检查实验进度"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 检查是否有结果文件
    png_files = [f for f in os.listdir('.') if f.startswith('longchain_vs_baseline_') and f.endswith('.png')]
    txt_files = [f for f in os.listdir('.') if f.startswith('longchain_vs_baseline_report_') and f.endswith('.txt')]
    
    if png_files and txt_files:
        print("=" * 80)
        print("✅ 实验完成！")
        print("=" * 80)
        print(f"图表文件: {png_files[0]}")
        print(f"报告文件: {txt_files[0]}")
        print("=" * 80)
        return True
    else:
        # 检查Python进程
        result = os.popen('tasklist /FI "IMAGENAME eq python.exe" 2>nul').read()
        python_count = result.count('python.exe')
        
        print(f"[{timestamp}] 实验仍在运行中...")
        print(f"Python进程数: {python_count}")
        print("预计还需: 10-20分钟")
        return False

if __name__ == '__main__':
    print("开始监控实验进度...")
    print("=" * 80)
    
    check_count = 0
    while True:
        check_count += 1
        print(f"\n--- 检查 #{check_count} ---")
        
        if check_progress():
            break
        
        # 每30秒检查一次
        time.sleep(30)
        
        # 最多检查60次（30分钟）
        if check_count >= 60:
            print("监控超时，但实验可能仍在继续...")
            break
