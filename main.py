from flask import Flask, request, Response
from flask_talisman import Talisman
from threading import Thread
import requests
import os
import time

# --- 核心配置 ---
FLASK_PORT = 8080
STREAMLIT_PORT = 8501
STREAMLIT_HOST = '127.0.0.1'  # 强制 Streamlit 只在本地监听

# --- Flask 智能门卫 ---
app = Flask('')

# 使用 Talisman 插件来处理 HTTPS 代理
# (这是实现反向代理的关键，即使内容安全策略为空)
Talisman(app, content_security_policy=None)

# 这个路由是给 UptimeRobot 的“心跳”
@app.route('/healthz')
def health_check():
    return "OK", 200

# 这个路由处理所有其他的请求，并将它们代理到 Streamlit
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def reverse_proxy(path):
    # 构建指向内部 Streamlit 服务的 URL
    streamlit_url = f"http://{STREAMLIT_HOST}:{STREAMLIT_PORT}/{path}"

    try:
        # 发起请求到 Streamlit
        resp = requests.request(
            method=request.method,
            url=streamlit_url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True # 使用流式传输以处理大文件和实时更新
        )

        # 将 Streamlit 的响应头和内容原封不动地返回给用户
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        # 返回一个流式响应
        return Response(resp.iter_content(chunk_size=1024), resp.status_code, headers)

    except requests.exceptions.ConnectionError:
        # 如果 Streamlit 还没有启动好，给用户一个友好的等待页面
        return "Streamlit is starting up, please refresh in a few seconds...", 503

# --- 启动器函数 ---
def run_flask():
    print(f">>> Flask is running on port {FLASK_PORT}")
    app.run(host='0.0.0.0', port=FLASK_PORT)

def run_streamlit():
    print(f">>> Starting Streamlit on port {STREAMLIT_PORT}")
    # 注意：我们强制 Streamlit 监听本地地址
    command = f"streamlit run app.py --server.port {STREAMLIT_PORT} --server.address {STREAMLIT_HOST}"
    os.system(command)

# --- 主执行部分 ---
if __name__ == '__main__':
    # 创建并启动 Streamlit 线程
    streamlit_thread = Thread(target=run_streamlit)
    streamlit_thread.daemon = True  # 设置为守护线程，主程序退出时它也退出
    streamlit_thread.start()

    # 给 Streamlit 一点启动时间
    print(">>> Waiting for Streamlit to initialize...")
    time.sleep(5) 

    # 启动 Flask 主程序
    run_flask()