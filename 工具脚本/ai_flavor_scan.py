# -*- coding: utf-8 -*-
"""
AI味扫描脚本 — 降AI体系检测闭环
规则对齐：标准/降AI规则.md（中文AI味特征库）
用法：python ai_flavor_scan.py <文章文件路径>
输出：AI浓度分（0-100，写手圈安全线<20）+ 逐项明细 + 修改建议
说明：启发式评分，判断"哪些痕迹存在"，不是精密检测器。
"""
import sys
import re
import os

sys.stdout.reconfigure(encoding="utf-8")

# ============ 规则词表（对应特征库章节） ============
# 特征库一·1.2 万能总起（固定短语）
TOTAL_OPENERS = ["在当今", "众所周知", "不可否认", "值得注意的是",
                 "令人惊讶的是", "毫无疑问", "不得不说", "值得一提的是", "当今社会"]
# 特征库一·1.2 万能总起（句式模式）
TOTAL_OPEN_PATTERNS = [re.compile(r"在这个.{0,20}的时代"), re.compile(r"随着.{0,30}的发展")]
# 特征库一·1.3 万能总结
TOTAL_CLOSERS = ["总而言之", "综上所述", "由此可见", "总之"]
# 特征库一·1.4 抽象黑话
BUZZWORDS = ["赋能", "闭环", "颗粒度", "底层逻辑", "抓手", "对齐", "拉通",
             "深度剖析", "认知升级", "复利思维", "降维打击", "躬身入局"]
# 特征库一·1.5 泛化引用
VAGUE_ATTRIB = ["研究表明", "许多专家认为", "数据显示", "业内普遍认为", "有观点认为",
                "众多专家指出", "很多专家"]
# 特征库二·2.2 假坦率开场（句首出现才计）
FAKE_CANDOR = ["说实话", "坦率讲", "坦率地讲", "讲真", "讲真的"]
# 特征库二·2.2 帮腔结语 / 口号式号召
SYCOPHANT_END = ["希望对你有所帮助", "希望对你有启发", "希望能帮到你", "希望可以帮到你",
                 "希望对大家有帮助", "让我们一起", "让我们一起努力"]
# 特征库二·2.3 万能比喻
UNIVERSAL_METAPHOR = ["就像一场旅行", "如同春天的花朵", "如同一盏明灯", "仿佛打开了新世界的大门",
                      "如同一把钥匙", "像一座灯塔", "宛如一场"]
# 特征库一·1.6 情绪形容词堆砌
EMOTION_ADJ = ["很焦虑", "非常焦虑", "特别焦虑", "非常失望", "特别失望", "十分失望",
               "特别开心", "非常开心", "十分开心", "非常愤怒", "特别愤怒", "十分愤怒",
               "非常激动", "特别激动", "十分沮丧", "非常沮丧"]
# 特征库一·1.1 连接词（频率红线）
CONNECTOR_LIMITS = {"此外": 2, "另外": 2, "同时": 2, "当然": 1, "确实": 1, "其实": 1,
                    "然而": 3, "但是": 4}
PARA_START_BAN = ["首先", "其次", "最后", "然后", "接着"]
# 特征库二·2.1 句式
NOT_A_BUT_B = re.compile(r"不是.{1,30}?，?而是")
NOT_ONLY_BUT = re.compile(r"不仅是.{1,30}?，?更是")
SELF_Q = ["那问题来了", "那么问题来了"]
GOLD_SENT = ["这，就是", "这就是", "这便是"]  # 金句病：每段强收对仗
# 特征库五 编排
# （加粗/emoji/编号嵌套由人工检查，脚本只查段落墙）

# ============ 读取 ============
def read_file(path):
    for enc in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError("无法识别文件编码")

# ============ 分析 ============
def analyze(text):
    hits = []          # (类型, 位置片段, 得分, 特征库章节)
    score = 0.0
    # 剥离HTML注释（自检记录等元数据不算正文）
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    n_chars = max(len(re.sub(r"\s", "", text)), 1)

    def hit(cat, snippet, pts, sec):
        nonlocal score
        hits.append((cat, snippet, pts, sec))
        score += pts

    # --- 段落 ---
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    # --- 句子 ---
    sentences = [s for s in re.split(r"[。！？!?\n]", text) if s.strip()]

    # 1. 词表类
    for w in TOTAL_OPENERS:
        n = text.count(w)
        if n: hit("万能总起", f"「{w}」×{n}", 2.0 * n, "特征库一·1.2")
    for pat in TOTAL_OPEN_PATTERNS:
        n = len(pat.findall(text))
        if n: hit("万能总起句式", f"「{pat.pattern}」×{n}", 2.0 * n, "特征库一·1.2")
    for w in TOTAL_CLOSERS:
        n = text.count(w)
        if n: hit("万能总结", f"「{w}」×{n}", 2.5 * n, "特征库一·1.3")
    for w in BUZZWORDS:
        n = text.count(w)
        if n: hit("抽象黑话", f"「{w}」×{n}", 1.2 * n, "特征库一·1.4")
    for w in VAGUE_ATTRIB:
        n = text.count(w)
        if n: hit("泛化引用", f"「{w}」×{n}", 2.0 * n, "特征库一·1.5")
    for w in EMOTION_ADJ:
        n = text.count(w)
        if n: hit("情绪形容词", f"「{w}」×{n}", 0.5 * n, "特征库一·1.6")
    for w in UNIVERSAL_METAPHOR:
        n = text.count(w)
        if n: hit("万能比喻", f"「{w}」×{n}", 2.0 * n, "特征库二·2.3")
    for w in SYCOPHANT_END:
        n = text.count(w)
        if n: hit("帮腔结语/口号", f"「{w}」×{n}", 2.5 * n, "特征库二·2.2")
    for w in SELF_Q:
        n = text.count(w)
        if n: hit("自问自答", f"「{w}」×{n}", 1.5 * n, "特征库二·2.2")
    for w in GOLD_SENT:
        n = text.count(w)
        if n: hit("金句病", f"「{w}」×{n}", 1.5 * n, "特征库二·2.4")

    # 2. 假坦率开场（句首）
    for s in sentences:
        s2 = s.lstrip("“\"' ")
        for w in FAKE_CANDOR:
            if s2.startswith(w):
                hit("假坦率开场", f"「{s2[:18]}…」", 1.5, "特征库二·2.2")
                break

    # 3. 连接词频率红线
    for w, limit in CONNECTOR_LIMITS.items():
        n = text.count(w)
        if n > limit:
            hit("连接词超限", f"「{w}」×{n}（红线≤{limit}）", 1.0 * (n - limit), "特征库一·1.1")
    for p in paras:
        for w in PARA_START_BAN:
            if p.startswith(w):
                hit("段落开头禁用词", f"「{p[:16]}…」以「{w}」开头", 2.0, "特征库一·1.1")

    # 4. 句式
    n1 = len(NOT_A_BUT_B.findall(text))
    if n1:
        hit("不是A而是B", f"×{n1}", 1.0 * n1 + (2.0 if n1 >= 3 else 0), "特征库二·2.1")
    n2 = len(NOT_ONLY_BUT.findall(text))
    if n2:
        hit("不仅是更是", f"×{n2}", 1.0 * n2, "特征库二·2.1")

    # 5. 排比组（连续3句以上同开头）
    groups = 0
    i = 0
    while i < len(sentences) - 2:
        a, b, c = sentences[i][:2], sentences[i+1][:2], sentences[i+2][:2]
        if a == b == c and len(a.strip()) >= 2 and a.strip() not in ("就是", "所以"):
            groups += 1
            i += 3
        else:
            i += 1
    if groups:
        hit("排比组", f"连续同开头×{groups}组", 2.5 * groups, "特征库二·2.1")

    # 6. 统计层（特征库二·2.4 量化阈值）
    lens = [len(s) for s in sentences if len(s) >= 2]
    if len(lens) >= 5:
        win = 0
        for i in range(len(lens) - 4):
            w5 = lens[i:i+5]
            if max(w5) - min(w5) <= 8:
                win += 1
        if win:
            hit("句长均匀窗口", f"连续5句长度差≤8字 ×{win}窗", 0.8 * win, "特征库二·2.4")
        long_n = sum(1 for L in lens if L > 40)
        if long_n:
            hit("超长句", f">40字 ×{long_n}", 0.3 * long_n, "特征库二·2.4")

    colon_d = text.count("：") * 100 / n_chars
    if colon_d >= 1.5:
        hit("冒号密度", f"{colon_d:.2f}次/百字（红线1.5）", 3.0, "特征库二·2.4")
    dash_d = (text.count("—") + text.count("——")) * 1000 / n_chars
    if dash_d >= 3:
        hit("破折号密度", f"{dash_d:.2f}个/千字（红线3）", 3.0, "特征库二·2.4")
    quote_n = text.count("“") + text.count("”") + text.count("\"")
    if len(paras) and quote_n / max(len(paras), 1) > 2:
        hit("双引号密度", f"每段{quote_n/max(len(paras),1):.1f}处（红线2）", 2.0, "特征库二·2.4")

    # 7. 结构层（特征库三）
    plens = [len(p) for p in paras]
    if len(plens) >= 5:
        m, sd = sum(plens)/len(plens), (sum((x-sum(plens)/len(plens))**2 for x in plens)/len(plens))**0.5
        if m and sd / m < 0.5:
            hit("段落长度均匀", f"每段≈{m:.0f}字±{sd:.0f}（信息密度无起伏）", 3.0, "特征库三·信息密度")
    for p in paras:
        if len(p) > 150:
            hit("段落墙", f"单段{len(p)}字无空行", 2.0, "特征库五·空行呼吸")
            break

    score = min(100.0, round(score, 1))
    return score, hits, len(paras), len(sentences)

# ============ 输出 ============
def render(score, hits, n_paras, n_sents, fname):
    lines = []
    lines.append("=" * 56)
    lines.append(f"AI味扫描报告：{os.path.basename(fname)}")
    lines.append(f"规模：{n_paras} 段 / {n_sents} 句")
    lines.append("-" * 56)
    if score < 20:
        level = "✅ 安全区（<20%）"
    elif score < 40:
        level = "⚠️ 警戒区（20-40%），建议降一轮再发"
    else:
        level = "❌ 高危区（>40%），先过一遍去AI味改写"
    lines.append(f"AI浓度分：{score} / 100 → {level}")
    lines.append("-" * 56)
    if hits:
        by_cat = {}
        for cat, snip, pts, sec in hits:
            by_cat.setdefault(cat, []).append((snip, pts, sec))
        for cat, items in by_cat.items():
            total = round(sum(p for _, p, _ in items), 1)
            lines.append(f"▍{cat}（合计+{total}）")
            for snip, pts, sec in items:
                lines.append(f"    {snip}  → {sec}")
    else:
        lines.append("未命中任何痕迹。要么是真人写的，要么词表该更新了。")
    lines.append("-" * 56)
    lines.append("提示：分数是启发式参考。命中项请对照特征库章节逐条判断，")
    lines.append("声纹优先——你本人语料里的用法不算AI味（特征库零章）。")
    lines.append("=" * 56)
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("用法：python ai_flavor_scan.py <文章文件路径>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"文件不存在：{path}")
        sys.exit(1)
    text = read_file(path)
    score, hits, np_, ns = analyze(text)
    print(render(score, hits, np_, ns, path))

if __name__ == "__main__":
    main()
