import os
import arxiv
import tarfile
import requests
import re
from datetime import datetime, timedelta
# --- 配置 ---
SEARCH_QUERY = 'abs: "Large Language Models" AND (abs: "Architecture" OR abs: "System")'
MAX_RESULTS = 10 
SYSTEM_PROMPT = "你是一个计算机领域的专家，请你根据文章的abstraction和conclusion，提炼出这篇文章做了什么，怎么做的，好在哪里。"
# GitHub Models 的配置
ENDPOINT = "https://models.inference.ai.azure.com"
MODEL_NAME = "DeepSeek-V3" # 或者 "DeepSeek-V3"，根据你 GitHub Models 权限确定

def extract_sections(tex_content):
    """从 LaTeX 源码中寻找摘要和结论"""
    abstract = ""
    abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', tex_content, re.DOTALL | re.IGNORECASE)
    if abs_match:
        abstract = abs_match.group(1).strip()
    
    conclusion = ""
    concl_match = re.search(r'\\section\{Conclusion\}(.*?)(\\section|\d|\\bibliog|\\end\{document\})', tex_content, re.DOTALL | re.IGNORECASE)
    if concl_match:
        conclusion = concl_match.group(1).strip()
    
    if not abstract and not conclusion:
        return f"无法精确解析 LaTeX 结构，提供部分正文：\n{tex_content[:4000]}"
    
    return f"【Abstract】: {abstract}\n\n【Conclusion】: {conclusion}"

def get_tex_content(arxiv_id):
    """下载 arXiv 源码包并提取主 .tex 文件"""
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    try:
        response = requests.get(url, timeout=30)
        with open("tmp.tar.gz", "wb") as f:
            f.write(response.content)
        with tarfile.open("tmp.tar.gz") as tar:
            tex_files = [m for m in tar.getmembers() if m.name.endswith('.tex')]
            if not tex_files: return ""
            main_tex = max(tex_files, key=lambda x: x.size)
            f = tar.extractfile(main_tex)
            return f.read().decode('utf-8', errors='ignore')
    except:
        return ""
    finally:
        if os.path.exists("tmp.tar.gz"): os.remove("tmp.tar.gz")
"""
def call_github_model(title, content):
    token = os.getenv("GH_MODELS_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"论文标题: {title}\n\n内容:\n{content}"}
        ],
        "temperature": 0.1 # 专家模式建议低随机性
    }
    
    try:
        res = requests.post(f"{ENDPOINT}/chat/completions", json=payload, headers=headers)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"GitHub Model 调用失败: {e}"
"""

def call_github_model(title, content):
    token = os.getenv("GH_MODELS_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 策略：将系统提示词和用户内容合并，减少 400 报错概率
    full_prompt = f"{SYSTEM_PROMPT}\n\n以下是论文信息：\n标题: {title}\n内容片段: {content}"

    payload = {
        "model": "DeepSeek-R1", # 请确保你在 GitHub Models 页面看到的是这个名字
        "messages": [
            {"role": "user", "content": full_prompt}
        ]
        # 暂时去掉 temperature 等参数，使用默认值以排除干扰
    }

    try:
        res = requests.post(f"{ENDPOINT}/chat/completions", json=payload, headers=headers)

        if res.status_code != 200:
            # 关键：返回详细的错误信息，帮助定位是内容太长了还是参数不对
            return f"GitHub Model 报错 (状态码 {res.status_code}): {res.text}"

        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Python 请求异常: {e}"
def main():
    client = arxiv.Client()
    search = arxiv.Search(
        query=SEARCH_QUERY,
        max_results=MAX_RESULTS,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    
    results = list(client.results(search))
    if not results:
        print("未发现论文")
        return

    md_content = f"# 每日论文深度分析 ({results[0].updated.strftime('%Y-%m-%d')})\n\n"

    for i, paper in enumerate(results, 1):
        print(f"正在处理 [{i}/{MAX_RESULTS}]: {paper.title}")
        tex = get_tex_content(paper.get_short_id())
        # 如果下载源码失败，则退而求其次使用 arxiv 自带的摘要
        extracted = extract_sections(tex) if tex else f"【Abstract (API)】: {paper.summary}"
        
        summary = call_github_model(paper.title, extracted)
        
        md_content += f"## {i}. {paper.title}\n"
        md_content += f"- **链接**: {paper.entry_id}\n"
        md_content += f"### 专家点评\n{summary}\n\n---\n"

    today = datetime.now().strftime('%Y-%m-%d')
    with open(f'RESEARCH_REPORT_{today}.md', "w", encoding="utf-8") as f:
        f.write(md_content)

if __name__ == "__main__":
    main()
