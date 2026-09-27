"""竞赛内容数据：73 个在中国真实存在的大学生竞赛 + 由其阶梯生成的行动卡 id。

纯数据 + 查询函数，不依赖 renpy，不读写文件。

约定（改数据前先读 `docs/CONTENT_SPEC.md` 第 4 节）：
- 竞赛 id 形如 ``c_xxx``；``c_`` 之后**不允许再出现下划线**，
  因为行动卡 id 是用 ``a_contest_{contest_id[2:]}_{tier}`` 拼出来的，
  多一个下划线就分不清哪一段是竞赛名、哪一段是阶梯。
- ``strengths`` / ``normal_bonus`` 的 key 只能是 ``config.ATTRS`` 里的属性名，权重为正数。
- ``tiers`` 必须是 ``config.CONTEST_TIERS`` 的**严格递增子序列**，至少两阶。
- 国赛 / 国际赛只配给重量级竞赛，普通竞赛给到省赛为止。

字段名与顺序是下游契约（actions.py 会照着读），不要改动、不要重排。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config as C


# ================================================================ 数据结构


@dataclass(frozen=True)
class Contest:
    """一个真实存在的竞赛。"""

    id: str                      # c_acm
    name: str                    # ACM-ICPC
    full_name: str               # 国际大学生程序设计竞赛
    majors: tuple[str, ...]      # 哪些大专业类能看见（通常 1 个）
    is_flex: bool                # True = 相邻专业类也能看见
    tiers: tuple[str, ...]       # 能打到哪几阶
    strengths: dict[str, float]  # 权重，如 {"portfolio": 3, "research": 1}
    normal_bonus: dict[str, int]  # 拿奖时额外给的属性点，可以为空字典
    team: bool                   # 是否组队
    note: str                    # 一句真实感的说明（什么时候打、怎么打）
    certs: tuple[str, ...]       # 相关的证，没有就给 ()


# ================================================================ 专业类邻接

# 这里不能 import majors（只允许 import config），所以专业 id 就地声明一份，
# 用途仅限自检与 flex 展开。
_MAJOR_IDS: tuple[str, ...] = ("cs", "mech", "civil", "sci", "biz", "ocean", "med", "hum")

# 相邻专业类：A 的 flex 竞赛，B 也能看见。关系是对称的。
_NEIGHBORS: dict[str, tuple[str, ...]] = {
    "cs": ("mech", "sci", "biz"),
    "mech": ("cs", "civil", "sci"),
    "civil": ("mech", "ocean", "sci"),
    "sci": ("cs", "mech", "civil", "biz", "ocean", "med"),
    "biz": ("cs", "sci", "hum"),
    "ocean": ("civil", "sci", "med"),
    "med": ("sci", "ocean"),
    "hum": ("biz",),
}

# 面向全校的竞赛：8 个专业类都能看见。
_ALL_MAJORS: tuple[str, ...] = _MAJOR_IDS


# ================================================================ 数据


CONTEST_LIST: tuple[Contest, ...] = (
    # ---------------------------------------------------------- 计算机与电子信息
    Contest(
        id="c_acm",
        name="ACM-ICPC",
        full_name="国际大学生程序设计竞赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national", "intl"),
        strengths={"portfolio": 3.0, "research": 1.0, "mind": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="九月打网络预选赛，十一月区域赛现场赛五小时十道题、三人共用一台电脑，想进队得先在校内选拔里排到前面。",
        certs=("软考中级（软件设计师）",),
    ),
    Contest(
        id="c_ccpc",
        name="CCPC",
        full_name="中国大学生程序设计竞赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="分站赛通常在十月到十一月，和 ICPC 亚洲区同期，很多学校把它当成区域赛之前的热身。",
        certs=(),
    ),
    Contest(
        id="c_lanqiao",
        name="蓝桥杯",
        full_name="蓝桥杯全国软件和信息技术专业人才大赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=False,
        note="秋天报名、次年四月省赛，个人赛按研究生与本科 A/B 组分开，填空和编程各占一半，拿了省一才有六月国赛的资格。",
        certs=("软考中级（软件设计师）",),
    ),
    Contest(
        id="c_cccc",
        name="CCCC 天梯赛",
        full_name="中国高校计算机大赛·团体程序设计天梯赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "mind": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="每年三月底开赛，十人一队按 10 分一档的阶梯题计分，一道题集体卡住总分就上不去，赛前两个月得天天刷题。",
        certs=(),
    ),
    Contest(
        id="c_ecdesign",
        name="全国大学生电子设计竞赛",
        full_name="全国大学生电子设计竞赛",
        majors=("cs", "mech"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0, "body": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="两年一届、奇数年办，八月的四天三夜封闭赛，题目当天公布，做完还要现场测试和答辩，控制类和仪器类各选一题。",
        certs=(),
    ),
    Contest(
        id="c_jsjdesign",
        name="中国大学生计算机设计大赛",
        full_name="中国大学生计算机设计大赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="四月校赛、五月省赛、七月国赛，分软件应用与开发、数媒设计、人工智能等大类，作品要现场演示并回答评委提问。",
        certs=(),
    ),
    Contest(
        id="c_infosec",
        name="全国大学生信息安全竞赛",
        full_name="全国大学生信息安全竞赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="春季线上初赛是 CTF 解题，三四人分工做题，八月到承办高校打线下决赛，还要交一份作品设计文档。",
        certs=("华为 HCIA-Security",),
    ),
    Contest(
        id="c_huaweict",
        name="华为 ICT 大赛",
        full_name="华为 ICT 大赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national", "intl"),
        strengths={"portfolio": 2.0, "intern": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="校内选拔之后打省赛，中国区总决赛在年中，实践赛要现场配设备、做组网和排障，考的就是 HCIA/HCIP 那套东西。",
        certs=("华为 HCIA-Datacom", "华为 HCIP-Datacom"),
    ),
    Contest(
        id="c_icchuang",
        name="全国大学生集成电路创新创业大赛",
        full_name="全国大学生集成电路创新创业大赛",
        majors=("cs", "mech"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="按企业命题分组（芯片设计、FPGA、EDA 等），要交完整的设计报告和版图，答辩时企业评委问得很细。",
        certs=(),
    ),
    Contest(
        id="c_bigdata",
        name="中国高校计算机大赛·大数据挑战赛",
        full_name="中国高校计算机大赛·大数据挑战赛",
        majors=("cs",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 2.0},
        normal_bonus={"research": 1},
        team=True,
        note="线上提交、按榜单排名，前期做特征工程最花时间，最后要在答辩里讲清楚模型为什么有效。",
        certs=("CDA 数据分析师 Level Ⅰ",),
    ),
    Contest(
        id="c_outsource",
        name="服创大赛",
        full_name="中国大学生服务外包创新创业大赛",
        majors=("cs", "biz"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "intern": 1.0, "network": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="企业出题、队伍在一个学期内交付可运行的系统，决赛现场演示加答辩，评委多是发包公司的工程师。",
        certs=(),
    ),
    Contest(
        id="c_internetplus",
        name="中国国际大学生创新大赛",
        full_name="中国国际大学生创新大赛（原“互联网+”大学生创新创业大赛）",
        majors=_ALL_MAJORS,
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "network": 2.0, "leadership": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="校赛在春季，省赛复赛要交商业计划书和路演视频，国赛现场答辩分金银铜，队里最好同时有做技术和会讲的人。",
        certs=(),
    ),
    Contest(
        id="c_tiaozhan",
        name="挑战杯",
        full_name="“挑战杯”全国大学生课外学术科技作品竞赛",
        majors=_ALL_MAJORS,
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 2.0, "leadership": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="奇数年办课外学术科技作品竞赛、偶数年办创业计划竞赛，要交研究报告或商业计划书，校赛一般在大二下启动。",
        certs=(),
    ),
    Contest(
        id="c_matmodel",
        name="全国大学生数学建模竞赛",
        full_name="全国大学生数学建模竞赛（CUMCM）",
        majors=("cs", "sci", "mech", "civil", "ocean", "biz"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "gpa": 2.0, "mind": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="九月开学第一周周四早上八点开赛、连做三天，A/B/C 三题选一交一篇论文，三个人里至少要有一个会写作的。",
        certs=("CDA 数据分析师 Level Ⅰ",),
    ),
    Contest(
        id="c_mcm",
        name="MCM/ICM",
        full_name="美国大学生数学建模竞赛",
        majors=("cs", "sci", "biz", "mech", "civil", "ocean"),
        is_flex=False,
        tiers=("school", "intl"),
        strengths={"english": 2.0, "research": 2.0, "mind": 1.0},
        normal_bonus={"english": 1},
        team=True,
        note="美赛在寒假二月，四天时间全英文写作，题目偏开放性建模，报名费按队收，多数学校会先办校内选拔再报销。",
        certs=(),
    ),
    # ---------------------------------------------------------- 机械与能源动力
    Contest(
        id="c_mechinnov",
        name="全国大学生机械创新设计大赛",
        full_name="全国大学生机械创新设计大赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="两年一届、偶数年办，主题每届换一次（如智慧家居、仿生机械），要交实物样机并现场演示动作，制作周期起码一个学期。",
        certs=(),
    ),
    Contest(
        id="c_gongxun",
        name="全国大学生工程训练综合能力竞赛",
        full_name="全国大学生工程训练综合能力竞赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "body": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="两年一届，赛项有无碳小车、智能物流机器人等，比的是加工精度和现场调试，赛前要在工程训练中心泡一两个月。",
        certs=(),
    ),
    Contest(
        id="c_advgraphics",
        name="“高教杯”先进成图大赛",
        full_name="“高教杯”全国大学生先进成图技术与产品信息建模创新大赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="分成尺规绘图和三维建模两块，机考之后还有现场答辩，赛前要把 SolidWorks 或 UG 的快捷键练到不用想。",
        certs=(),
    ),
    Contest(
        id="c_smartcar",
        name="全国大学生智能汽车竞赛",
        full_name="全国大学生智能汽车竞赛",
        majors=("mech", "cs"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0, "mind": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="分电磁、摄像头、越野等组别，暑假不回家在实验室调车是常态，八月跑分赛区、九月打全国总决赛。",
        certs=(),
    ),
    Contest(
        id="c_chemdesign",
        name="全国大学生化工设计竞赛",
        full_name="全国大学生化工设计竞赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="三月拿到设计任务书，整队要完成工艺流程、设备选型、经济核算和三维厂区，八月国赛答辩现场回答工艺问题。",
        certs=(),
    ),
    Contest(
        id="c_jieneng",
        name="全国大学生节能减排社会实践与科技竞赛",
        full_name="全国大学生节能减排社会实践与科技竞赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 2.0},
        normal_bonus={"research": 1},
        team=True,
        note="先交作品申报书和科技查新报告，通过网评才有八月决赛，作品必须能算清一年的节能量或减排量。",
        certs=(),
    ),
    Contest(
        id="c_zhoupeiyuan",
        name="周培源大学生力学竞赛",
        full_name="全国周培源大学生力学竞赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"gpa": 2.0, "research": 2.0},
        normal_bonus={"gpa": 1},
        team=False,
        note="两年一届、奇数年的五月考个人赛，考的是理论力学和材料力学的硬功夫，名次靠前还能被选进七月的团体赛。",
        certs=(),
    ),
    Contest(
        id="c_robomaster",
        name="RoboMaster 机甲大师赛",
        full_name="全国大学生机器人大赛 RoboMaster 机甲大师赛",
        majors=("mech", "cs"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0, "leadership": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="机器人要自己造，机械、电控、视觉算法全队分工，赛季从秋季校内赛一路打到夏季分区赛和全国赛。",
        certs=(),
    ),
    Contest(
        id="c_robocon",
        name="全国大学生机器人大赛 RoboCon",
        full_name="全国大学生机器人大赛 RoboCon",
        majors=("mech", "cs"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="每年出一道新规则、主题年年换，队伍要在一个学年里从零做出两台能对抗的机器人，通宵改结构是常事。",
        certs=(),
    ),
    Contest(
        id="c_fsc",
        name="中国大学生方程式汽车大赛",
        full_name="中国大学生方程式汽车大赛（FSC）",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "intern": 1.0, "network": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="每年十月比赛，要交设计、成本和商务报告，还要跑直线加速、八字环绕和耐久赛，车队通常提前一年开始拉赞助。",
        certs=(),
    ),
    Contest(
        id="c_mechcx",
        name="中国大学生机械工程创新创意大赛",
        full_name="中国大学生机械工程创新创意大赛",
        majors=("mech",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="下含过程装备实践与创新、铸造工艺设计、材料热处理创新创业等赛项，按赛项分别报名，交设计报告加实物或仿真。",
        certs=(),
    ),
    # ---------------------------------------------------------- 土木与水利
    Contest(
        id="c_structure",
        name="全国大学生结构设计竞赛",
        full_name="全国大学生结构设计竞赛",
        majors=("civil",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0, "body": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="校赛用竹皮和白卡纸做模型，加载前称重、加载后测位移，十月到承办高校打国赛，越轻又越能扛才拿分。",
        certs=(),
    ),
    Contest(
        id="c_structureit",
        name="全国大学生结构设计信息技术大赛",
        full_name="全国大学生结构设计信息技术大赛",
        majors=("civil",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="在电脑上对着真实工程建模配筋，要交计算书和施工图，考的是平法识图准不准、建模快不快。",
        certs=("全国 BIM 技能等级考试（一级）",),
    ),
    Contest(
        id="c_shuili",
        name="全国大学生水利创新设计大赛",
        full_name="全国大学生水利创新设计大赛",
        majors=("civil",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="两年一届，作品围绕节水灌溉、水生态修复和智慧水务，决赛要带实物模型到现场做水工演示。",
        certs=(),
    ),
    Contest(
        id="c_hangxingqi",
        name="全国海洋航行器设计与制作大赛",
        full_name="全国海洋航行器设计与制作大赛",
        majors=("civil", "ocean"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "research": 1.0, "body": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="分设计制作与竞速两类，要自己造船体、装推进器和控制系统，比赛当天下水跑圈，翻船了就现场修。",
        certs=(),
    ),
    Contest(
        id="c_cehui",
        name="全国大学生测绘技能竞赛",
        full_name="全国大学生测绘技能竞赛",
        majors=("civil",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "body": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="分导线测量、水准测量和数字测图，四人一组轮换仪器，误差超限直接扣分，练的是外业手速和内业平差。",
        certs=(),
    ),
    Contest(
        id="c_bim",
        name="“广联达杯”BIM 毕业设计创新大赛",
        full_name="“广联达杯”全国高校 BIM 毕业设计创新大赛",
        majors=("civil",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"portfolio": 2.0, "intern": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="用广联达系列软件建一栋完整建筑，从土建到机电再到场布，先过网络晋级赛才能进全国总决赛答辩。",
        certs=("全国 BIM 技能等级考试（一级）",),
    ),
    Contest(
        id="c_nongshui",
        name="“华维杯”农业水利创新设计大赛",
        full_name="“华维杯”全国大学生农业水利工程及相关专业创新设计大赛",
        majors=("civil",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"portfolio": 2.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="题目多是灌区改造或智能灌溉系统，先交申报书过网评，进决赛后带模型到现场答辩。",
        certs=(),
    ),
    # ---------------------------------------------------------- 数学与自然科学
    Contest(
        id="c_math",
        name="全国大学生数学竞赛",
        full_name="全国大学生数学竞赛",
        majors=("sci",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"gpa": 3.0, "exam": 1.0},
        normal_bonus={"gpa": 1},
        team=False,
        note="每年十月预赛、次年三月决赛，分数学类和非数学类，非数学类只考高等数学，数学类要考数学分析和高代。",
        certs=(),
    ),
    Contest(
        id="c_yau",
        name="丘成桐大学生数学竞赛",
        full_name="丘成桐大学生数学竞赛",
        majors=("sci",),
        is_flex=True,
        tiers=("national", "intl"),
        strengths={"gpa": 3.0, "research": 2.0},
        normal_bonus={"research": 2},
        team=False,
        note="按分析与微分方程、几何与拓扑等六个方向分别报名，先笔试再口试，进总决赛的对手很多来自清北和中科大。",
        certs=(),
    ),
    Contest(
        id="c_phys",
        name="全国大学生物理实验竞赛",
        full_name="全国大学生物理实验竞赛",
        majors=("sci",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "portfolio": 2.0},
        normal_bonus={"research": 1},
        team=True,
        note="两年一届，要自己设计实验、录数据、写论文式报告，决赛现场做实验并接受评委追问误差来源。",
        certs=(),
    ),
    Contest(
        id="c_cupt",
        name="中国大学生物理学术竞赛",
        full_name="中国大学生物理学术竞赛（CUPT）",
        majors=("sci",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "english": 1.0, "mind": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="本质是物理辩论赛，抽到题目后要做一个月研究，赛场上分正方、反方和评论方轮流发言，英语好还能打国际赛。",
        certs=(),
    ),
    Contest(
        id="c_chem",
        name="全国大学生化学实验创新设计大赛",
        full_name="全国大学生化学实验创新设计大赛",
        majors=("sci",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "portfolio": 2.0},
        normal_bonus={"research": 1},
        team=True,
        note="分七个赛区，作品是自拟的实验方案，要交实验视频和论文，赛区前几名才能进全国总决赛。",
        certs=(),
    ),
    Contest(
        id="c_lifesci",
        name="全国大学生生命科学竞赛",
        full_name="全国大学生生命科学竞赛",
        majors=("sci", "med"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"research": 3.0, "portfolio": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="分科学探究和创新创业两类，探究类要真进实验室做一年课题，交原始实验记录和论文，网评过了才现场答辩。",
        certs=(),
    ),
    Contest(
        id="c_statmodel",
        name="全国大学生统计建模大赛",
        full_name="全国大学生统计建模大赛",
        majors=("sci", "biz"),
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "gpa": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="三四月报名、六月交论文，题目从给定的几个方向里选，评审最看重数据来源可不可靠、模型假设说没说清。",
        certs=("CDA 数据分析师 Level Ⅰ",),
    ),
    # ---------------------------------------------------------- 经济管理
    Contest(
        id="c_bizplan",
        name="全国大学生商业策划大赛",
        full_name="全国大学生商业策划大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "network": 1.0, "leadership": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="要求组队做一个完整项目：市场调研、财务测算、风险分析缺一不可，决赛路演十分钟加评委提问五分钟。",
        certs=(),
    ),
    Contest(
        id="c_diaocha",
        name="全国大学生市场调查与分析大赛",
        full_name="全国大学生市场调查与分析大赛（正大杯）",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "network": 1.0, "portfolio": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="先过网考知识赛，再组队做实地调研、写报告，省赛答辩之后进全国总决赛，问卷回收量是硬指标。",
        certs=("CDA 数据分析师 Level Ⅰ",),
    ),
    Contest(
        id="c_finance",
        name="全国大学生金融投资模拟大赛",
        full_name="全国大学生金融投资模拟大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "intern": 1.0, "exam": 1.0},
        normal_bonus={"portfolio": 1},
        team=False,
        note="用虚拟账户做实盘模拟，按收益率和最大回撤排名，部分赛段还要交一份投资策略报告。",
        certs=("证券从业资格", "基金从业资格"),
    ),
    Contest(
        id="c_accounting",
        name="全国大学生会计与商业案例大赛",
        full_name="全国大学生会计与商业案例大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"intern": 2.0, "english": 1.0},
        normal_bonus={"intern": 1},
        team=True,
        note="给一份真实企业的财报，限时做完分析并给出决策建议，全英文赛段也很常见，赛前要练快速读报表。",
        certs=("初级会计职称",),
    ),
    Contest(
        id="c_wuliu",
        name="全国大学生物流设计大赛",
        full_name="全国大学生物流设计大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"portfolio": 2.0, "intern": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="两年一届，题目由物流企业出，要交方案设计书和仿真结果，决赛答辩通常由企业高管当评委。",
        certs=(),
    ),
    Contest(
        id="c_qiyemo",
        name="全国企业竞争模拟大赛",
        full_name="全国企业竞争模拟大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "leadership": 1.0, "network": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="在系统里经营一家虚拟公司，几个季度一轮，比的是定价、产能和现金流的平衡，队伍一般三到四人。",
        certs=(),
    ),
    Contest(
        id="c_erp",
        name="全国大学生 ERP 沙盘模拟大赛",
        full_name="全国大学生 ERP 沙盘模拟经营大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"leadership": 2.0, "intern": 1.0},
        normal_bonus={"leadership": 1},
        team=True,
        note="一张盘面模拟六年经营，财务、采购、生产、销售各一人，资金链断在当年就直接出局。",
        certs=("初级会计职称",),
    ),
    Contest(
        id="c_sanchuang",
        name="全国大学生电子商务“三创赛”",
        full_name="全国大学生电子商务“创新、创意及创业”挑战赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "network": 1.0, "intern": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="从校赛打到省赛再到国赛，要交项目计划书和路演 PPT，评委最爱问的是「你们的第一批用户从哪来」。",
        certs=(),
    ),
    Contest(
        id="c_cbec",
        name="全国大学生跨境电商创新创业能力大赛",
        full_name="OCALE 全国大学生跨境电商创新创业能力大赛",
        majors=("biz",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"intern": 2.0, "english": 1.0, "portfolio": 1.0},
        normal_bonus={"intern": 1},
        team=True,
        note="用真实平台数据做选品和运营方案，含选品报告、店铺装修与直播脚本，决赛要现场模拟一轮运营。",
        certs=(),
    ),
    # ---------------------------------------------------------- 海洋与水产
    Contest(
        id="c_oceanknow",
        name="全国海洋知识竞赛",
        full_name="全国大中学生海洋知识竞赛",
        majors=("ocean",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 1.0, "english": 1.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=False,
        note="先在线答题，内容涵盖海洋生物、物理海洋和海洋权益，进决赛之后有现场抢答和主题演讲环节。",
        certs=(),
    ),
    Contest(
        id="c_shuichan",
        name="全国大学生水产类专业实践能力竞赛",
        full_name="全国大学生水产类专业实践能力竞赛",
        majors=("ocean",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 1.0, "body": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="考的是真本事：认鱼虾贝藻、解剖、测水质、做饲料配方，实验室操作的分比笔试占得更多。",
        certs=(),
    ),
    Contest(
        id="c_watertest",
        name="全国大学生水质检测技能竞赛",
        full_name="全国大学生水质检测技能竞赛",
        majors=("ocean",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=False,
        note="按国标方法测氨氮、总磷和溶解氧，从采样、加药到记录原始数据全程计时，操作不规范直接扣分。",
        certs=(),
    ),
    Contest(
        id="c_environ",
        name="全国大学生环境生态科技创新大赛",
        full_name="全国大学生环境生态科技创新大赛",
        majors=("ocean",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "portfolio": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="要交一份能落地的方案，比如河道生态修复或固废资源化，决赛评委常追问成本和日处理量。",
        certs=(),
    ),
    Contest(
        id="c_yujingying",
        name="“渔菁英”挑战赛",
        full_name="“渔菁英”全国大学生水产技能挑战赛",
        majors=("ocean",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"portfolio": 2.0, "body": 1.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="围绕水产养殖考苗种培育、病害防治和养殖方案设计，常在养殖基地现场操作，暑假得下水干活。",
        certs=(),
    ),
    Contest(
        id="c_marineart",
        name="全国大学生海洋文化创意设计大赛",
        full_name="全国大中学生海洋文化创意设计大赛",
        majors=("ocean",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"portfolio": 2.0, "mind": 1.0},
        normal_bonus={"portfolio": 1},
        team=False,
        note="接受海报、插画、文创和短视频，围绕海洋主题创作，先线上评审再进现场展览。",
        certs=(),
    ),
    # ---------------------------------------------------------- 医学与生命科学
    Contest(
        id="c_clinical",
        name="全国大学生临床技能竞赛",
        full_name="全国大学生医学技术技能大赛（临床技能竞赛）",
        majors=("med",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "body": 1.0, "mind": 1.0},
        normal_bonus={"portfolio": 2},
        team=True,
        note="在模拟人上考问诊、查体、穿刺和急救，站式考核限时完成，赛前要在技能中心练到手熟。",
        certs=("执业医师资格证",),
    ),
    Contest(
        id="c_medtech",
        name="全国大学生医学技术技能大赛",
        full_name="全国大学生医学技术技能大赛",
        majors=("med",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "research": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="按检验、影像、康复等专业分组，考的是仪器操作和结果判读，两个台次之间只隔几分钟。",
        certs=(),
    ),
    Contest(
        id="c_tcm",
        name="全国中医药技能大赛",
        full_name="全国中医药技能大赛",
        majors=("med",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "gpa": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="考中药辨识、方剂和针灸推拿手法，认药环节蒙着眼靠闻和摸，赛前要背几百味药。",
        certs=(),
    ),
    Contest(
        id="c_nursing",
        name="全国大学生护理技能大赛",
        full_name="全国大学生护理技能大赛",
        majors=("med",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "body": 1.0, "mind": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="考无菌操作、静脉输液和心肺复苏，每一步都有评分表，超时或者漏步骤都要扣分。",
        certs=("护士执业资格证",),
    ),
    Contest(
        id="c_biochem",
        name="全国大学生生物化学实验创新设计大赛",
        full_name="全国大学生生物化学实验创新设计大赛",
        majors=("med",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"research": 2.0, "portfolio": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="要自己设计实验并跑出结果，交实验记录和论文，答辩时老师会追问对照组为什么这么设。",
        certs=(),
    ),
    Contest(
        id="c_pharm",
        name="全国医药院校药学/中药学专业大学生实验技能竞赛",
        full_name="全国医药院校药学/中药学专业大学生实验技能竞赛",
        majors=("med",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"research": 2.0, "portfolio": 1.0},
        normal_bonus={"portfolio": 1},
        team=False,
        note="考称量、提取、含量测定和仪器分析，药物分析部分要现场算回收率，误差超出范围就丢分。",
        certs=("执业药师",),
    ),
    Contest(
        id="c_basicmed",
        name="全国大学生基础医学创新研究暨实验设计论坛",
        full_name="全国大学生基础医学创新研究暨实验设计论坛",
        majors=("med",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"research": 3.0, "portfolio": 1.0},
        normal_bonus={"research": 1},
        team=True,
        note="提交的是自己做的课题，海报展示加现场答辩，很多参赛作品后来直接变成了保研用的科研经历。",
        certs=(),
    ),
    # ---------------------------------------------------------- 人文社科
    Contest(
        id="c_fltrp",
        name="“外研社·国才杯”大学生外语能力大赛",
        full_name="“外研社·国才杯”全国大学生外语能力大赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"english": 3.0, "mind": 1.0},
        normal_bonus={"english": 1},
        team=False,
        note="分演讲、写作、阅读、翻译四个赛项，校赛在秋季、省赛复赛在十月，演讲赛要现场抽题即兴发挥。",
        certs=("CATTI 三级笔译",),
    ),
    Contest(
        id="c_neccs",
        name="全国大学生英语竞赛",
        full_name="全国大学生英语竞赛（NECCS）",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"english": 2.0, "exam": 1.0},
        normal_bonus={"english": 1},
        team=False,
        note="每年四月初赛、五月决赛，分 A/B/C/D 四类，题型里有智力题和写作，C 类（非英语专业本科）报考的人最多。",
        certs=(),
    ),
    Contest(
        id="c_debate",
        name="全国大学生辩论赛",
        full_name="全国大学生辩论赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"mind": 1.0, "english": 1.0, "network": 1.0, "portfolio": 1.0},
        normal_bonus={"mind": 1},
        team=True,
        note="四人一队，赛前一周才公布辩题，赛制是立论、质询、自由辩论加总结，临场反应比稿子重要。",
        certs=(),
    ),
    Contest(
        id="c_speech",
        name="全国大学生演讲大赛",
        full_name="全国大学生演讲大赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"mind": 2.0, "network": 1.0},
        normal_bonus={"mind": 1},
        team=False,
        note="分命题演讲和即兴演讲两轮，即兴部分抽题后只有几分钟准备，评委卡时间，超时直接扣分。",
        certs=(),
    ),
    Contest(
        id="c_moot",
        name="全国高校模拟法庭大赛",
        full_name="全国高校模拟法庭大赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "national"),
        strengths={"portfolio": 2.0, "exam": 1.0, "english": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="按真实庭审视程走，队伍分原告被告，要写书状并在庭上举证质证，评委多是执业律师和法官。",
        certs=("法律职业资格证",),
    ),
    Contest(
        id="c_legal",
        name="全国大学生法律职业能力大赛",
        full_name="全国大学生法律职业能力大赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"exam": 2.0, "portfolio": 1.0},
        normal_bonus={"exam": 1},
        team=False,
        note="考案例分析、法律文书写作和现场辩论，题目多改编自真实判例，赛前要把民法典翻熟。",
        certs=("法律职业资格证",),
    ),
    Contest(
        id="c_adart",
        name="全国大学生广告艺术大赛",
        full_name="全国大学生广告艺术大赛（大广赛）",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 3.0, "mind": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="三到六月按命题创作，平面、视频、策划案分赛道，企业命题会指定品牌和卖点，获奖作品能直接进作品集。",
        certs=(),
    ),
    Contest(
        id="c_teacher",
        name="师范生教学技能竞赛",
        full_name="全国师范院校师范生教学技能竞赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"leadership": 2.0, "english": 1.0, "mind": 1.0},
        normal_bonus={"leadership": 1},
        team=False,
        note="现场抽课题、限时备课写教案，再做十分钟片段教学，板书和普通话都在评分表里。",
        certs=("教师资格证", "普通话水平测试二级甲等"),
    ),
    Contest(
        id="c_volunteer",
        name="中国青年志愿服务项目大赛",
        full_name="中国青年志愿服务项目大赛",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"network": 1.0, "leadership": 1.0, "mind": 1.0},
        normal_bonus={"mind": 1},
        team=True,
        note="先交项目书和一年以上的服务记录，进决赛要做路演，评委关心的是这个项目能不能持续做下去。",
        certs=(),
    ),
    Contest(
        id="c_artshow",
        name="全国大学生艺术展演",
        full_name="全国大学生艺术展演活动",
        majors=("hum",),
        is_flex=True,
        tiers=("school", "prov", "national"),
        strengths={"portfolio": 2.0, "mind": 1.0},
        normal_bonus={"portfolio": 1},
        team=True,
        note="三年一届，分声乐、器乐、舞蹈、戏剧和艺术作品，先在校内艺术团排练，再代表学校去省里展演。",
        certs=(),
    ),
    Contest(
        id="c_careerplan",
        name="全国大学生职业规划大赛",
        full_name="全国大学生职业规划大赛",
        majors=_ALL_MAJORS,
        is_flex=False,
        tiers=("school", "prov", "national"),
        strengths={"mind": 1.0, "exam": 1.0, "network": 1.0},
        normal_bonus={"mind": 1},
        team=False,
        note="要交一份完整的职业规划书并做路演，评委爱问「你为这个目标具体做过什么」，空话会被当场拆穿。",
        certs=(),
    ),
)


CONTESTS: dict[str, Contest] = {contest.id: contest for contest in CONTEST_LIST}


# ================================================================ 阶梯与行动卡

def stage_card_id(contest_id: str, tier: str) -> str:
    """竞赛的某一阶对应的行动卡 id：``a_contest_{id 去掉 c_ 前缀}_{tier}``。

    竞赛 id 里除 ``c_`` 前缀外不能再有下划线，否则拼出来的卡 id 会有歧义。
    """
    if not contest_id.startswith("c_"):
        raise ValueError(f"竞赛 id 必须以 c_ 开头：{contest_id}")
    if "_" in contest_id[2:]:
        raise ValueError(f"竞赛 id 除 c_ 前缀外不能再含下划线：{contest_id}")
    if tier not in C.CONTEST_TIERS:
        raise ValueError(f"非法竞赛阶梯：{tier}")
    return f"a_contest_{contest_id[2:]}_{tier}"


CONTEST_LADDER: dict[str, tuple[str, ...]] = {
    contest.id: contest.tiers for contest in CONTEST_LIST
}

STAGE_CARDS: dict[str, dict[str, str]] = {
    contest.id: {
        tier: stage_card_id(contest.id, tier) for tier in contest.tiers
    }
    for contest in CONTEST_LIST
}


# ================================================================ 查询

def get(contest_id: str) -> Contest:
    """按 id 取竞赛。id 不存在时抛 KeyError。"""
    try:
        return CONTESTS[contest_id]
    except KeyError:
        raise KeyError(f"未知竞赛 id：{contest_id}") from None


def for_major(major_id: str) -> list[Contest]:
    """该专业类能看见的全部竞赛：本专业 + 相邻专业放出来的 flex 竞赛。"""
    if major_id not in _MAJOR_IDS:
        raise KeyError(f"未知专业类 id：{major_id}")
    neighbors = _NEIGHBORS.get(major_id, ())
    visible: list[Contest] = []
    for contest in CONTEST_LIST:
        if major_id in contest.majors:
            visible.append(contest)
        elif contest.is_flex and any(
            other in contest.majors for other in neighbors
        ):
            visible.append(contest)
    return visible


def dedicated(major_id: str) -> list[Contest]:
    """专属竞赛：``majors`` 里只有这一个专业类。"""
    if major_id not in _MAJOR_IDS:
        raise KeyError(f"未知专业类 id：{major_id}")
    return [c for c in CONTEST_LIST if c.majors == (major_id,)]


def flex(contest_id: str) -> bool:
    """这个竞赛是否向相邻专业类开放。"""
    return get(contest_id).is_flex


def all_ids() -> tuple[str, ...]:
    """全部竞赛 id，顺序固定（宣言顺序）。"""
    return tuple(contest.id for contest in CONTEST_LIST)


def tier_gate_attr(contest_id: str) -> str:
    """这个竞赛拿奖概率主要看哪个属性（strengths 里权重最高的那个）。"""
    strengths = get(contest_id).strengths
    return max(strengths.items(), key=lambda item: item[1])[0]


# ================================================================ 自检

def _validate() -> None:
    """导入时跑一遍内容自检。数据写错要立刻炸，而不是等玩家点出来。"""
    seen: set[str] = set()
    for contest in CONTEST_LIST:
        if contest.id in seen:
            raise ValueError(f"竞赛 id 重复：{contest.id}")
        seen.add(contest.id)

        stage_card_id(contest.id, contest.tiers[0])  # 顺带校验 id 命名规则

        if len(contest.tiers) < 2:
            raise ValueError(f"{contest.id} 至少要能打两阶，当前 {contest.tiers}")
        positions: list[int] = []
        for tier in contest.tiers:
            if tier not in C.CONTEST_TIER_ORDER:
                raise ValueError(f"{contest.id} 含非法阶梯：{tier}")
            positions.append(C.CONTEST_TIER_ORDER[tier])
        if positions != sorted(positions) or len(set(positions)) != len(positions):
            raise ValueError(
                f"{contest.id} 的 tiers 必须是 {C.CONTEST_TIERS} 的严格递增子序列，"
                f"当前 {contest.tiers}"
            )

        if not contest.majors:
            raise ValueError(f"{contest.id} 至少要给一个专业类")
        for major_id in contest.majors:
            if major_id not in _MAJOR_IDS:
                raise ValueError(f"{contest.id} 含非法专业类：{major_id}")

        for key, weight in contest.strengths.items():
            if key not in C.ATTRS:
                raise ValueError(f"{contest.id} 的 strengths 含非法属性：{key}")
            if weight <= 0:
                raise ValueError(f"{contest.id} 的 strengths 权重必须为正：{key}={weight}")
        for key, value in contest.normal_bonus.items():
            if key not in C.ATTRS:
                raise ValueError(f"{contest.id} 的 normal_bonus 含非法属性：{key}")
            if value <= 0:
                raise ValueError(f"{contest.id} 的 normal_bonus 必须为正：{key}={value}")

        for text in (contest.name, contest.full_name, contest.note):
            if not text.strip():
                raise ValueError(f"{contest.id} 有空文案")

    for major_id in _MAJOR_IDS:
        visible = [c for c in CONTEST_LIST if major_id in c.majors]
        own = [c for c in CONTEST_LIST if c.majors == (major_id,)]
        if len(visible) < 6:
            raise ValueError(f"{major_id} 只有 {len(visible)} 个可见竞赛，至少要 6 个")
        if len(own) < 3:
            raise ValueError(f"{major_id} 只有 {len(own)} 个专属竞赛，至少要 3 个")


_validate()
