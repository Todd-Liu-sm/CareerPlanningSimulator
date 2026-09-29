"""生成 game/core/actions.py。

    python tools/gen_actions.py

为什么要生成器：内容量大，手写会漂移。内容压在上面的表里，
跑一遍生成一致的 actions.py。

玩家反馈驱动的设计原则：
  * 选项要**粗** —— 「娱乐」「休息」「社交」这种粒度，不要细分活动。
  * 一个学期十几张卡就够，每学期挑 3 个。
  * 竞赛不写具体比赛名，只有大类（科研类/工程类/综合类…）。
  * 单卡效果总和 <= 6，避免某个属性数值爆炸。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "game" / "core" / "actions.py"


# ================================================================ 内容表
#
# 通用卡：(id, 名称, 品质, sem_lo, sem_hi, 描述, effects, tags, extra)
# extra 可含 flags=() / gate={} / hobby=(key,xp) / note=""

GENERAL: list[tuple] = [
    # ---------------- 学业 ----------------
    ("a_study", "认真上课", "common", 1, 8,
     "把专业课当回事：坐前排、记笔记、课后把作业独立做完，不抄不拖。",
     {"gpa": 4, "mind": 1}, ("study", "gpa"), {}),
    ("a_final_sprint", "期末冲刺", "rare", 1, 8,
     "考前两周把整学期课件重新过一遍，往年题刷透，有问题直接去办公室问老师。",
     {"gpa": 5, "mind": 1}, ("study", "gpa"),
     {"note": "期末两周的效率，抵得上平时两个月。"}),
    ("a_english", "学英语", "common", 1, 8,
     "每天固定一小时：背单词、精听、跟读，把四六级当阶段目标一个个过掉。",
     {"english": 4, "gpa": 1}, ("english", "study"), {}),
    ("a_english_exam", "冲四六级", "rare", 1, 8,
     "把六级当成一个必须拿下的关卡：真题刷三遍，听力精听到能复述。",
     {"english": 5, "gpa": 1}, ("english", "study"), {}),
    ("a_english_speaking", "练口语听力", "common", 2, 8,
     "跟读、复述、找人练对话，把「看得懂」变成「说得出」。",
     {"english": 4, "mind": 1}, ("english", "mind"), {}),
    ("a_exam_drill", "刷题备考", "common", 2, 8,
     "按考试时间做整套模拟，掐表涂卡，把错题按类型整理成册反复看。",
     {"exam": 4, "mind": 1}, ("exam", "study"), {}),
    ("a_reading", "读专业书", "common", 1, 8,
     "跳出教材读一两本领域里公认的好书，把课上没讲透的地方自己补上。",
     {"research": 3, "gpa": 1}, ("research", "study"), {}),

    # ---------------- 科研 ----------------
    ("a_lab", "进实验室", "rare", 1, 8,
     "找老师要了个工位，跟着师兄跑实验、洗数据、整理结果，先学会怎么做事。",
     {"research": 4, "portfolio": 1}, ("research", "lab"),
     {"gate": {"gpa": 6}, "note": "进组最难的从来不是能力，是开口问。"}),
    ("a_paper", "写论文", "epic", 3, 8,
     "把做出来的东西写成一篇能投的稿子，改了七八遍，投出去等审稿意见。",
     {"research": 5, "portfolio": 1}, ("research", "portfolio"),
     {"gate": {"research": 10}}),

    # ---------------- 实习 / 就业 ----------------
    ("a_intern", "去实习", "rare", 2, 8,
     "挤地铁去公司上班，做的是真实项目，第一次知道「交付」两个字的重量。",
     {"intern": 4, "network": 1, "portfolio": 1}, ("intern", "work"),
     {"gate": {"gpa": 5}}),
    ("a_resume", "打磨简历", "common", 2, 8,
     "把经历一条条改成「做了什么 + 结果是什么」，找学长和 HR 各改一遍。",
     {"portfolio": 2, "intern": 2, "mind": 1}, ("work", "portfolio"), {}),
    ("a_project", "做项目", "common", 1, 8,
     "自己攒一个能拿得出手的项目，从需求到做完走一遍，过程写进作品集。",
     {"portfolio": 4, "intern": 1}, ("project", "portfolio"), {}),

    # ---------------- 竞赛选型 ----------------
    ("a_contest_pick", "竞赛选型", "rare", 2, 2,
     "把能打的比赛按大类列成表，对照强项和时间圈定方向，其余只当练手。",
     {"portfolio": 1, "mind": 2, "network": 1}, ("contest", "mind"),
     {"flags": ("contest_main_picked",),
      "note": "同时打五个比赛的人，通常一个奖也拿不到。"}),

    # ---------------- 社交 ----------------
    ("a_social", "社交", "common", 1, 8,
     "社团、班级、宿舍、饭局，认识一些跟你不像的人，也让人记住你。",
     {"network": 3, "mind": 1}, ("social", "network"), {}),
    ("a_club", "参加社团", "common", 1, 8,
     "报一个喜欢的社团，从搬桌子开始干，慢慢成了能张罗事的那个人。",
     {"network": 2, "leadership": 3}, ("social", "leadership"), {}),
    ("a_class_cadre", "当班委", "common", 1, 6,
     "竞选上班委，收作业传通知帮同学跑腿，事情琐碎但大家都记得你。",
     {"leadership": 3, "network": 2}, ("leadership", "social"), {}),
    ("a_speech", "练表达", "common", 1, 8,
     "上台讲、当众争论、把想法说清楚。害羞是真的，但这件事只能靠多说来破。",
     {"leadership": 2, "mind": 2, "english": 1}, ("leadership", "mind"), {}),

    # ---------------- 娱乐 / 休息（消疲劳） ----------------
    ("a_entertain", "娱乐放松", "common", 1, 8,
     "追剧、打游戏、刷视频，什么都不想，让自己彻底空一会儿。",
     {"mind": 3, "body": 1}, ("entertain", "mind"), {}),
    ("a_rest", "好好休息", "safe", 1, 8,
     "睡够觉、按时吃饭、把手机放远一点。什么都不做也是一种安排。",
     {"mind": 3, "body": 3}, ("rest", "body"), {}),
    ("a_routine", "按部就班", "safe", 1, 8,
     "不折腾、不掉队，课照上、作业照交，把这一段时间稳稳地过完。",
     {"gpa": 2, "mind": 2}, ("study", "gpa"), {}),
    ("a_catchup", "补补进度", "safe", 1, 8,
     "把落下的作业、没看的课件、欠下的实验报告一次性补齐，回到及格线以上。",
     {"gpa": 2, "mind": 1}, ("study", "gpa"), {}),
    ("a_sport", "运动", "common", 1, 8,
     "每周固定三次，跑步打球或者去健身房，把身体这块本钱存回来。",
     {"body": 4, "mind": 2}, ("sport", "body"), {}),
    ("a_sleep_fix", "调整作息", "common", 1, 8,
     "把凌晨两点的手机放下，按点睡按点起，两周之后整个人都不一样。",
     {"body": 3, "mind": 2, "gpa": 1}, ("rest", "body"), {}),

    # ---------------- 爱好（8 类各一张，**永久可选**，能一路升到 Lv4） ----------------
    #
    # 玩家反馈："所有爱好类卡牌都要一直存在，另外可以设置多个级别，
    # 修完就可以选下一个。"
    #
    # 所以爱好是**一条长线**而不是一次性机会卡：每类一张卡，1-8 学期都在，
    # 反复投同一张就一路升级（L1=1 次 / L2=3 次 / L3=5 次 / L4=8 次）。
    # 当前等级和还差多少次由 UI 直接印在卡上（见 bridge.hobby_track）。
    ("a_hobby_sport", "练体育运动", "common", 1, 8,
     "把一项运动练到能拿出来说的程度，顺便认识一帮固定一起练的人。",
     {"body": 3, "network": 1}, ("hobby", "sport"), {"hobby": ("sport", 15)}),
    ("a_hobby_art", "搞点创作", "common", 1, 8,
     "拍照、画画、写东西，做点不为了交差的东西，攒着攒着就成了作品。",
     {"mind": 2, "portfolio": 2}, ("hobby", "art"), {"hobby": ("art", 15)}),
    ("a_hobby_music", "玩音乐", "common", 1, 8,
     "练琴、组乐队、去唱歌，音乐是最容易认识人的爱好。",
     {"network": 2, "mind": 2}, ("hobby", "music"), {"hobby": ("music", 15)}),
    ("a_hobby_game", "打游戏", "common", 1, 8,
     "认真打一段时间游戏，放松是真的，但要小心它吃掉你的绩点。",
     {"mind": 3, "network": 1, "gpa": -1}, ("hobby", "gaming"),
     {"hobby": ("gaming", 15)}),
    ("a_hobby_read", "看书", "common", 1, 8,
     "读闲书、看纪录片、听播客。慢，但会改变你写东西的水平。",
     {"mind": 2, "english": 1, "exam": 1}, ("hobby", "reading"),
     {"hobby": ("reading", 15)}),
    ("a_hobby_screen", "看片", "common", 1, 8,
     "追剧看电影，看得多了会想自己说点什么，于是开始写影评。",
     {"mind": 2, "portfolio": 1}, ("hobby", "screen"), {"hobby": ("screen", 15)}),
    ("a_hobby_food", "做饭探店", "common", 1, 8,
     "学着做饭、找好吃的店，生活技能加社交货币，性价比很高。",
     {"body": 2, "network": 2}, ("hobby", "food"), {"hobby": ("food", 15)}),
    ("a_hobby_volunteer", "做志愿", "common", 1, 8,
     "支教、献血、赛事志愿，做点跟绩点无关但让你踏实的事。",
     {"leadership": 2, "network": 2, "mind": 1}, ("hobby", "volunteer"),
     {"hobby": ("volunteer", 15)}),

    # ---------------- 大三大四的冲刺 ----------------
    ("a_baoyan_pack", "准备保研材料", "rare", 5, 7,
     "成绩单、排名证明、推荐信、个人陈述，材料一样一样凑齐并扫描归档。",
     {"portfolio": 3, "research": 1, "english": 1}, ("portfolio", "study"),
     {"gate": {"gpa": 12}}),
    ("a_kaoyan", "考研复习", "rare", 5, 8,
     "数学、英语、专业课三轮推进，每天十小时，把图书馆坐成第二个宿舍。",
     {"exam": 5, "gpa": 1}, ("exam", "study"), {}),
    ("a_qiuzhao", "秋招投递", "rare", 5, 7,
     "宣讲会一场接一场，笔试面试连轴转，把被拒当成日常。",
     {"intern": 4, "network": 2}, ("work", "intern"), {}),
    ("a_xuandiao", "备考选调", "rare", 5, 8,
     "行测申论两科并进，同时盯紧各省的选调公告和报名窗口。",
     {"exam": 4, "leadership": 2}, ("exam", "party"), {}),
    ("a_abroad", "准备留学", "rare", 5, 8,
     "语言成绩、文书、推荐信、选校清单，每一步都不能拖到最后一刻。",
     {"english": 4, "research": 1, "portfolio": 1}, ("english", "study"), {}),
    ("a_thesis", "毕业设计", "safe", 7, 8,
     "把四年的东西收束成一份能答辩的成果：写、改、讲，然后结束。",
     {"gpa": 2, "research": 2, "mind": 2}, ("study", "research"), {}),
    ("a_graduation", "毕业告别", "safe", 8, 8,
     "散伙饭、合影、把宿舍清空。四年就这么过去了。",
     {"mind": 4, "network": 2}, ("rest", "mind"), {}),

    # ================================================================
    # 深度卡池
    # ================================================================
    #
    # 为什么需要这么多：门槛是"专精到 22-26"，而 24 个行动点全部押在一个
    # 属性上时，能拿到的点数 = 该属性最好的 8 张卡之和。原来每个属性只有
    # 3-5 张卡，合计 11-17 点，**没有任何一条结局门槛够得着**，所有专精
    # 玩法都会掉进兜底结局。这一批把每个属性补到 8-12 张。
    #
    # 单卡点数仍然 <= 6，靠"张数"而不是"单卡数值"来撑上限，
    # 这样多线铺开的玩家拿到的总量不会跟着膨胀。

    # ---------------- 学业（绩点） ----------------
    ("a_gpa_notes", "整理笔记", "common", 1, 8,
     "把一学期的课件缩成一叠自己的话，考前只看这一叠。",
     {"gpa": 3, "research": 1}, ("study", "gpa"), {}),
    ("a_gpa_group", "小组作业", "common", 1, 8,
     "抱一次大腿也当一次大腿，把团队作业的分稳稳拿下来。",
     {"gpa": 2, "network": 2}, ("study", "social"), {}),
    ("a_gpa_office", "找老师答疑", "common", 2, 8,
     "课后去办公室问问题，顺便让老师记住你的名字。",
     {"gpa": 3, "network": 1}, ("study", "social"), {}),
    ("a_gpa_mock", "往年题", "rare", 2, 8,
     "把近五年的卷子按题型拆开，找出老师每年都考的那几个点。",
     {"gpa": 4, "exam": 2}, ("study", "gpa"), {}),
    ("a_gpa_lesson", "补基础课", "common", 1, 6,
     "高数、线代、概率论，挂过一次才知道基础课有多贵。",
     {"gpa": 4, "mind": 1}, ("study", "gpa"), {}),
    ("a_gpa_project", "课程设计", "rare", 2, 8,
     "把一个课程大作业做成能写进简历的东西，而不是交完就删。",
     {"gpa": 3, "portfolio": 3}, ("study", "project"), {}),
    ("a_gpa_reduce", "少打点游戏", "common", 1, 8,
     "把每天两小时的开黑砍掉一半，绩点会替你把话说清楚。",
     {"gpa": 3, "mind": 1, "body": 1}, ("study", "mind"), {}),
    ("a_gpa_review", "复盘错题", "rare", 2, 8,
     "建一个错题本，按错因分类，考前只翻它。",
     {"gpa": 4, "research": 1}, ("study", "gpa"), {}),

    # ---------------- 科研 ----------------
    ("a_res_paper_read", "读文献", "common", 1, 8,
     "从综述读起，一周精读一篇，学会快速判断一篇论文值不值得读。",
     {"research": 4, "english": 1}, ("research", "study"), {}),
    ("a_res_lab_daily", "泡实验室", "rare", 2, 8,
     "没课就待在实验室，跑数据、修设备、跟师兄学怎么把事做完。",
     {"research": 4, "portfolio": 2}, ("research", "lab"), {}),
    ("a_res_data", "跑数据", "common", 2, 8,
     "清洗、标注、跑统计，科研里最枯燥也最见功底的部分。",
     {"research": 3, "portfolio": 1}, ("research", "lab"), {}),
    ("a_res_report", "写报告", "common", 2, 8,
     "把一次实验写成一页纸：目的、方法、结果、下一步。",
     {"research": 4, "gpa": 1}, ("research", "study"), {}),
    ("a_res_group", "课题组会", "common", 1, 8,
     "每周讲一次进展，被问住的地方就是下周要做的事。",
     {"research": 3, "network": 1, "mind": 1}, ("research", "lab"), {}),
    ("a_res_seminar", "听学术讲座", "common", 1, 8,
     "听完提问环节别急着走，前沿是怎么长出来的只有现场能感受到。",
     {"research": 3, "mind": 1}, ("research", "mind"), {}),
    ("a_res_survey", "做文献综述", "rare", 3, 8,
     "把一个方向的论文读成一张图，知道自己站在哪一格。",
     {"research": 5, "portfolio": 1}, ("research", "portfolio"),
     {"gate": {"research": 8}}),
    ("a_res_patent", "申请专利", "epic", 4, 8,
     "把手里那个小改进写成申请材料，等一次实质审查。",
     {"research": 4, "portfolio": 2}, ("research", "portfolio"),
     {"gate": {"research": 12}}),

    # ---------------- 外语 ----------------
    ("a_eng_words", "背单词", "common", 1, 8,
     "每天两百个，用打卡软件逼自己，别指望一次记住。",
     {"english": 3, "mind": 1}, ("english", "study"), {}),
    ("a_eng_listen", "精听听力", "common", 1, 8,
     "一句一句听写，直到每个连读都能对上。",
     {"english": 4, "mind": 1}, ("english", "study"), {}),
    ("a_eng_read", "看英文原著", "rare", 2, 8,
     "从自己感兴趣的小说开始，生词别查，先读完一本。",
     {"english": 4, "research": 1}, ("english", "research"), {}),
    ("a_eng_readaloud", "晨读英语", "common", 1, 8,
     "每天早上在操场读半小时，嘴皮子利索了耳朵也跟着好。",
     {"english": 3, "body": 1}, ("english", "body"), {}),
    ("a_eng_ielts", "考雅思托福", "rare", 2, 8,
     "报一次真考，把听说读写四项分报到目标线以上。",
     {"english": 5, "portfolio": 1}, ("english", "cert"),
     {"gate": {"english": 8}}),
    ("a_eng_corner", "英语角", "common", 1, 8,
     "每周去一次英语角，先敢开口，再谈流利。",
     {"english": 3, "network": 2}, ("english", "social"), {}),
    ("a_eng_translate", "做笔译", "rare", 3, 8,
     "接一点翻译的活，既能练语言又能赚点生活费。",
     {"english": 4, "portfolio": 2}, ("english", "portfolio"), {}),
    ("a_eng_cert", "考证书", "common", 2, 8,
     "四六级、专四专八、CATTI，能考的证一个个刷过去。",
     {"english": 4, "exam": 1}, ("english", "cert"), {}),

    # ---------------- 实习 ----------------
    ("a_int_seek", "投实习", "common", 2, 8,
     "把简历投到够得着的每一家，先拿到面试再说。",
     {"intern": 4, "mind": 1}, ("intern", "work"), {}),
    ("a_int_small", "小公司实习", "common", 2, 8,
     "从十几人的小公司做起，什么都干，成长反而快。",
     {"intern": 3, "portfolio": 2}, ("intern", "work"), {}),
    ("a_int_campus", "校园大使", "common", 1, 8,
     "帮公司做校内推广，简历上多一条，人脉也多一圈。",
     {"intern": 3, "network": 2, "leadership": 1}, ("intern", "social"), {}),
    ("a_int_follow", "跟一个项目", "rare", 2, 8,
     "跟着一个完整项目从立项走到上线，知道一次交付要踩多少坑。",
     {"intern": 4, "portfolio": 2}, ("intern", "project"), {}),
    ("a_int_referral", "找内推", "rare", 3, 8,
     "找学长和实习同事要内推码，比自己海投的效率高一个数量级。",
     {"intern": 3, "network": 3}, ("intern", "social"), {}),
    ("a_int_review", "实习复盘", "common", 2, 8,
     "把做过的活按「问题-动作-结果」写下来，面试时直接能讲。",
     {"intern": 3, "portfolio": 2, "mind": 1}, ("intern", "work"), {}),
    ("a_int_convert", "争取转正", "rare", 4, 8,
     "实习结束前把转正的事谈清楚，一份 offer 比十次面试有用。",
     {"intern": 5, "mind": 1}, ("intern", "work"),
     {"gate": {"intern": 10}}),
    ("a_int_cert", "考从业资格", "common", 2, 8,
     "证券、会计、教资，行业入门证考下来不亏。",
     {"intern": 2, "exam": 3}, ("intern", "cert"), {}),

    # ---------------- 应试 ----------------
    ("a_exam_mock", "模拟考试", "common", 2, 8,
     "按真实时间做整套题，涂卡、翻页、上厕所都按考场来。",
     {"exam": 4, "mind": 2}, ("exam", "mind"), {}),
    ("a_exam_math", "刷数学题", "rare", 2, 8,
     "数学是考研和行测的共同地基，一天不刷手就生。",
     {"exam": 5, "gpa": 1}, ("exam", "study"), {}),
    ("a_exam_essay", "练申论", "common", 3, 8,
     "一周一篇大作文，找范文拆结构，改到能用为止。",
     {"exam": 4, "mind": 1}, ("exam", "study"), {}),
    ("a_exam_logic", "练行测", "common", 3, 8,
     "资料分析、判断推理、言语理解，一个模块一个模块啃。",
     {"exam": 4, "mind": 1}, ("exam", "study"), {}),
    ("a_exam_pro", "专业课", "rare", 3, 8,
     "目标院校的指定教材和真题，翻到能背出目录。",
     {"exam": 5, "gpa": 1}, ("exam", "study"),
     {"gate": {"exam": 8}}),
    ("a_exam_interview", "练结构化面试", "rare", 4, 8,
     "对着镜子练、找人模拟，把答题框架刻进肌肉记忆。",
     {"exam": 4, "leadership": 2}, ("exam", "leadership"), {}),
    ("a_exam_timing", "掐时间做题", "common", 2, 8,
     "行测做不完是最大的失分点，练到每道题都有时间预算。",
     {"exam": 4, "mind": 1}, ("exam", "study"), {}),
    ("a_exam_review", "错题本", "common", 2, 8,
     "把错的题按类型抄下来，考前只看这个本子。",
     {"exam": 3, "gpa": 1}, ("exam", "study"), {}),

    # ---------------- 人脉 ----------------
    ("a_net_alumni", "联系学长学姐", "common", 1, 8,
     "请人喝杯咖啡，问问这条路真实的样子，很多弯路可以省掉。",
     {"network": 4, "mind": 1}, ("social", "network"), {}),
    ("a_net_teacher", "找导师聊", "rare", 2, 8,
     "带着问题去找老师，不是去要答案，是去要方向。",
     {"network": 3, "research": 2}, ("social", "research"), {}),
    ("a_net_team", "组队打比赛", "rare", 2, 8,
     "找几个互补的人一起干一件事，队友往往比奖状留得久。",
     {"network": 3, "portfolio": 2}, ("social", "contest"), {}),
    ("a_net_lecture", "听宣讲会", "common", 3, 8,
     "宣讲会上问一个具体问题，比递十份简历更容易被记住。",
     {"network": 3, "intern": 2}, ("social", "work"), {}),
    ("a_net_job_fair", "逛招聘会", "common", 3, 8,
     "一场场走下来，你会知道市场到底在为什么付钱。",
     {"network": 3, "intern": 2, "mind": 1}, ("social", "work"), {}),
    ("a_net_group", "混圈子", "common", 1, 8,
     "加群、参会、线上社区，信息差就是这么被抹平的。",
     {"network": 4, "mind": 1}, ("social", "network"), {}),
    ("a_net_mentor", "找引路人", "rare", 3, 8,
     "找到愿意带你的那个人，定期汇报进展，别只在有事时出现。",
     {"network": 4, "research": 2}, ("social", "research"), {}),
    ("a_net_keep", "维护老朋友", "common", 1, 8,
     "别只在需要帮忙时才联系，平时问候一句就够了。",
     {"network": 3, "mind": 2}, ("social", "mind"), {}),

    # ---------------- 影响力 ----------------
    ("a_lead_team", "带队做事", "rare", 2, 8,
     "从策划到分工到收尾，完整带一次队，才知道难在哪。",
     {"leadership": 3, "network": 2}, ("leadership", "social"), {}),
    ("a_lead_party", "递交入党申请", "rare", 2, 8,
     "写申请书、上党课、接受考察，这是一条要走两年的路。",
     {"leadership": 2, "mind": 2}, ("party", "leadership"),
     {"flags": ("party_applied",),
      "note": "越早递交，到大四才来得及转正。"}),
    ("a_lead_volunteer", "组织志愿活动", "common", 2, 8,
     "自己发起一次志愿活动，从找场地到招人全流程走一遍。",
     {"leadership": 3, "network": 2, "mind": 1}, ("leadership", "volunteer"), {}),
    ("a_lead_class", "竞选班委", "common", 1, 6,
     "站上讲台说三分钟，选上了就得把事做完。",
     {"leadership": 3, "network": 1}, ("leadership", "social"), {}),
    ("a_lead_club_core", "社团骨干", "rare", 2, 8,
     "从干事做到部长，学会怎么让别人愿意跟你一起干。",
     {"leadership": 3, "network": 2}, ("leadership", "social"), {}),
    ("a_lead_event", "办一场活动", "rare", 2, 8,
     "拉赞助、排流程、控现场，出一次纰漏就全学会了。",
     {"leadership": 4, "portfolio": 1}, ("leadership", "project"), {}),
    ("a_lead_public", "公开发言", "common", 1, 8,
     "争取每一次上台的机会，包括那些你觉得自己还没准备好的。",
     {"leadership": 3, "mind": 2}, ("leadership", "mind"), {}),
    ("a_lead_peer", "协调同学", "common", 1, 8,
     "调停一次宿舍矛盾、组织一次集体活动，都是影响力。",
     {"leadership": 2, "network": 2, "mind": 1}, ("leadership", "social"), {}),

    # ---------------- 作品 ----------------
    ("a_port_side", "做个小工具", "common", 1, 8,
     "解决自己一个真实的小麻烦，做出来给自己用。",
     {"portfolio": 3, "intern": 1}, ("project", "portfolio"), {}),
    ("a_port_write", "写作输出", "common", 1, 8,
     "把学到的东西写成文章发出去，被质疑是进步最快的方式。",
     {"portfolio": 3, "mind": 2}, ("project", "mind"), {}),
    ("a_port_github", "整理作品集", "common", 2, 8,
     "把做过的东西挑三个，删掉凑数的，写清楚每个解决了什么。",
     {"portfolio": 3, "intern": 2}, ("portfolio", "work"), {}),
    ("a_port_design", "做一个设计", "rare", 2, 8,
     "海报、界面、视频、模型，做出一个自己愿意反复看的成品。",
     {"portfolio": 4, "mind": 2}, ("project", "portfolio"), {}),
    ("a_port_comp", "参加小比赛", "common", 1, 8,
     "先拿校级奖项练手，知道评审真正在意什么。",
     {"portfolio": 3, "network": 1, "mind": 1}, ("contest", "portfolio"), {}),
    ("a_port_blog", "运营一个账号", "common", 1, 8,
     "持续输出一个方向的内容，把它当成你的公开简历。",
     {"portfolio": 3, "network": 2}, ("project", "social"), {}),
    ("a_port_award", "冲刺大奖", "epic", 3, 8,
     "把手里的项目打磨到能冲国家级奖项的水平，反复改到评审挑不出硬伤。",
     {"portfolio": 5, "research": 1}, ("contest", "portfolio"),
     {"gate": {"portfolio": 12}}),
    ("a_port_show", "做一次展示", "common", 2, 8,
     "把成果讲给不懂的人听，讲明白了才算真做明白。",
     {"portfolio": 3, "leadership": 2}, ("portfolio", "leadership"), {}),

    # ---------------- 身体 ----------------
    ("a_fit_run", "跑步", "common", 1, 8,
     "每周三次，从三公里开始，先把作息和心肺拉回来。",
     {"body": 4, "mind": 1}, ("sport", "body"), {}),
    ("a_fit_gym", "去健身房", "common", 1, 8,
     "力量训练是长期投入，半年后你会感谢现在的自己。",
     {"body": 4, "mind": 1}, ("sport", "body"), {}),
    ("a_fit_team", "打一场球", "common", 1, 8,
     "篮球、足球、羽毛球，运动顺便社交，性价比最高的选项。",
     {"body": 3, "network": 2}, ("sport", "social"), {}),
    ("a_fit_sleep", "早睡", "common", 1, 8,
     "十一点躺下，把手机放到够不着的地方。",
     {"body": 3, "mind": 2}, ("rest", "body"), {}),
    ("a_fit_diet", "好好吃饭", "common", 1, 8,
     "按时吃三餐，少吃外卖和夜宵，胃会替你把状态还回来。",
     {"body": 3, "mind": 1}, ("rest", "body"), {}),
    ("a_fit_outdoor", "去户外", "common", 1, 8,
     "爬山、骑行、露营，离开学校两天，回来什么都好说。",
     {"body": 3, "mind": 3}, ("sport", "mind"), {}),
    ("a_fit_checkup", "体检", "common", 2, 8,
     "每年做一次体检，身体的账别等到大四才还。",
     {"body": 2, "mind": 1}, ("rest", "body"), {}),
    ("a_fit_habit", "坚持一个习惯", "rare", 2, 8,
     "选一件小事坚持一百天，这件事本身就会改变你。",
     {"body": 4, "mind": 2}, ("sport", "mind"),
     {"gate": {"body": 8}}),

    # ---------------- 心态 ----------------
    ("a_mind_accept", "接受不完美", "common", 1, 8,
     "承认有些事就是做不到，然后把能做到的做完。",
     {"mind": 3, "body": 1}, ("mind", "rest"), {}),
    ("a_mind_talk", "找人聊聊", "common", 1, 8,
     "跟朋友、家人或者咨询师说说话，别一个人扛。",
     {"mind": 3, "network": 1}, ("mind", "social"), {}),
    ("a_mind_meditate", "冥想", "common", 1, 8,
     "每天十分钟，把注意力放回呼吸上，脑子会清爽很多。",
     {"mind": 3, "body": 1}, ("mind", "rest"), {}),
    ("a_mind_journal", "写日记", "common", 1, 8,
     "睡前把今天的事写三行，情绪从脑子里搬到纸上就轻了。",
     {"mind": 3}, ("mind", "rest"), {}),
    ("a_mind_pause", "给自己放假", "rare", 1, 8,
     "停一周，什么都不追，回来再看那些事没那么急。",
     {"mind": 5, "body": 1}, ("mind", "rest"), {}),
    ("a_mind_compare", "别跟人比", "common", 1, 8,
     "关掉朋友圈一段时间，你只需要跟去年的自己比。",
     {"mind": 3, "body": 1}, ("mind", "rest"), {}),
    ("a_mind_plan", "做长期规划", "rare", 2, 8,
     "把四年摊在一张纸上，标出每个节点，焦虑会变成待办事项。",
     {"mind": 3, "exam": 2}, ("mind", "study"), {}),
    ("a_mind_support", "当别人的支撑", "common", 1, 8,
     "陪一个状态不好的朋友走一段，你会发现自己也没那么脆。",
     {"mind": 2, "network": 3}, ("mind", "social"), {}),
]


# 专业专属卡：(id, 名称, 品质, sem_lo, sem_hi, 专业, 描述, effects, tags, extra)
MAJOR: list[tuple] = [
    # ---------------- cs ----------------
    ("a_cs_code", "刷题写代码", "common", 1, 8, "cs",
     "每天固定刷几道题，把数据结构和算法练成肌肉记忆。",
     {"portfolio": 4, "research": 1}, ("project", "portfolio"), {}),
    ("a_cs_stack", "啃技术栈", "common", 1, 8, "cs",
     "挑一个方向往深里做：后端、前端、客户端或算法，做出能演示的东西。",
     {"portfolio": 3, "intern": 2}, ("project", "work"), {}),
    ("a_cs_bigtech", "冲大厂实习", "rare", 3, 8, "cs",
     "投递、笔试、几轮面试，把项目和八股都准备到能对答如流。",
     {"intern": 5, "portfolio": 1}, ("intern", "work"),
     {"gate": {"portfolio": 8}}),
    ("a_cs_oss", "参与开源", "rare", 2, 8, "cs",
     "给开源项目提第一个 patch，学会读别人的代码、按规范提 PR。",
     {"portfolio": 3, "research": 2, "network": 1}, ("project", "portfolio"), {}),

    # ---------------- mech ----------------
    ("a_mech_draw", "练制图建模", "common", 1, 8, "mech",
     "二维图、三维建模、装配与仿真，把工程语言练到能直接交活。",
     {"portfolio": 3, "gpa": 1}, ("project", "study"), {}),
    ("a_mech_shop", "下车间", "common", 1, 8, "mech",
     "金工实习、数控、3D 打印，手上沾油才知道图纸和实物差多远。",
     {"portfolio": 3, "body": 2}, ("project", "body"), {}),
    ("a_mech_design", "做一台机器", "rare", 2, 8, "mech",
     "从方案到零件到装配，真做出一个能动的东西，拿去打工程类竞赛。",
     {"portfolio": 5, "research": 1}, ("project", "portfolio"),
     {"gate": {"portfolio": 7}}),

    # ---------------- civil ----------------
    ("a_civil_survey", "测量与工地", "common", 1, 8, "civil",
     "扛着仪器跑野外、下工地，把课本上的力学和真实结构对上号。",
     {"portfolio": 3, "body": 2}, ("project", "body"), {}),
    ("a_civil_soft", "学工程软件", "common", 1, 8, "civil",
     "把结构计算和 BIM 建模练熟，能独立出一套完整的图。",
     {"portfolio": 3, "gpa": 1}, ("project", "study"), {}),
    ("a_civil_design", "做结构设计", "rare", 2, 8, "civil",
     "组队做一次完整的结构设计：选型、计算书、模型，拿去打结构类竞赛。",
     {"portfolio": 5, "research": 1}, ("project", "portfolio"),
     {"gate": {"portfolio": 7}}),

    # ---------------- sci ----------------
    ("a_sci_proof", "啃基础课", "common", 1, 8, "sci",
     "数学分析、高等代数、物理，把证明和推导一遍遍重写到自己能讲出来。",
     {"gpa": 4, "research": 2}, ("study", "gpa"), {}),
    ("a_sci_model", "打建模竞赛", "rare", 1, 8, "sci",
     "组队打数学建模：选题、建模、编程、写作，三天三夜出成果。",
     {"portfolio": 4, "research": 2}, ("contest", "portfolio"), {}),
    ("a_sci_lab", "做实验", "common", 2, 8, "sci",
     "进课题组做实验或者推公式，把课本上的结论亲手复现一遍。",
     {"research": 4, "portfolio": 1}, ("research", "lab"),
     {"gate": {"gpa": 7}}),

    # ---------------- biz ----------------
    ("a_biz_reading", "读行业报告", "common", 1, 8, "biz",
     "把券商和咨询的行业报告当课外书读，学着用数据讲清楚一个行业。",
     {"research": 2, "exam": 2, "network": 1}, ("study", "research"), {}),
    ("a_biz_case", "做商业案例", "common", 1, 8, "biz",
     "拿真实公司做案例：拆财报、算市场、给方案，练到能路演。",
     {"portfolio": 3, "exam": 1}, ("project", "portfolio"), {}),
    ("a_biz_intern", "去公司实习", "rare", 2, 8, "biz",
     "券商、银行、四大或互联网，做真实的分析和报表，学会在 deadline 前交付。",
     {"intern": 5, "network": 1}, ("intern", "work"),
     {"gate": {"gpa": 6}}),
    ("a_biz_cert", "考从业证书", "common", 2, 8, "biz",
     "初级会计、证券从业、基金从业，一科一科考下来，简历上多两行。",
     {"exam": 3, "portfolio": 2}, ("cert", "exam"), {}),
    ("a_biz_network", "混行业圈子", "common", 2, 8, "biz",
     "听讲座、加群、找学长聊，知道这个行业到底在招什么样的人。",
     {"network": 4, "intern": 1}, ("social", "network"), {}),

    # ---------------- ocean ----------------
    ("a_ocean_field", "出海实习", "rare", 1, 8, "ocean",
     "跟船出海采样、记录数据，晕船是真的，但那些数据只有海上才有。",
     {"research": 4, "body": 2}, ("research", "body"), {}),
    ("a_ocean_skill", "练专业技能", "common", 1, 8, "ocean",
     "水质检测、生物鉴定、海洋调查规范，把野外作业的基本功练扎实。",
     {"research": 3, "portfolio": 2}, ("research", "lab"), {}),
    ("a_ocean_policy", "读政策文件", "common", 2, 8, "ocean",
     "把海洋相关的规划和政策文件读一遍，知道这个领域国家在往哪投钱。",
     {"research": 2, "exam": 2, "leadership": 1}, ("study", "research"), {}),

    # ---------------- med ----------------
    ("a_med_reading", "读医学文献", "common", 1, 8, "med",
     "从综述读起，学着看懂一篇论文在解决什么问题、结论可不可靠。",
     {"research": 3, "english": 1}, ("research", "study"), {}),
    ("a_med_basic", "啃医学基础", "common", 1, 8, "med",
     "解剖、生理、病理、生化，背下来还要能串起来，这是后面所有课的地基。",
     {"gpa": 4, "research": 1}, ("study", "gpa"), {}),
    ("a_med_clinical", "练临床技能", "rare", 2, 8, "med",
     "问诊、查体、穿刺、缝合，一项项过关，手上功夫是练出来的。",
     {"portfolio": 4, "body": 2}, ("project", "portfolio"), {}),
    ("a_med_clerkship", "去医院见习", "rare", 3, 8, "med",
     "跟着带教老师进病房，第一次面对真实病人，也第一次知道医生有多累。",
     {"intern": 4, "mind": 2}, ("intern", "work"), {}),

    # ---------------- hum ----------------
    ("a_hum_language", "练外语", "common", 1, 8, "hum",
     "精读、泛读、听说译，把外语练到能当工具用，而不只是考试科目。",
     {"english": 4, "gpa": 1}, ("english", "study"), {}),
    ("a_hum_write", "写东西", "common", 1, 8, "hum",
     "写作、评论、剧本、策划，把想法写成别人愿意读完的东西。",
     {"portfolio": 3, "mind": 2}, ("project", "portfolio"), {}),
    ("a_hum_debate", "练辩论表达", "common", 1, 8, "hum",
     "打辩论、做演讲、参加模拟法庭，逼自己把逻辑和表达都练出来。",
     {"leadership": 3, "mind": 2, "english": 1}, ("leadership", "mind"), {}),
    ("a_hum_law", "备考法考", "rare", 4, 8, "hum",
     "法考三门一起上，客观题加主观题，一年之内把这条路走通。",
     {"exam": 4, "gpa": 1}, ("exam", "study"), {}),
]


# ================================================================ 渲染

def _fmt_dict(d) -> str:
    if not d:
        return "{}"
    return "{" + ", ".join("%r: %r" % (k, v) for k, v in d.items()) + "}"


def _fmt_tuple(t) -> str:
    if not t:
        return "()"
    if len(t) == 1:
        return "(%r,)" % (t[0],)
    return "(" + ", ".join(repr(x) for x in t) + ")"


def _render(cid, name, rarity, lo, hi, major, text, effects, tags, extra) -> str:
    """渲染成一个 _mk(...) 调用。关键字参数统一放在收尾那行。"""
    kw = []
    if major:
        kw.append("major=%r" % major)
    if tags:
        kw.append("tags=%s" % _fmt_tuple(tags))
    for key in ("flags",):
        if extra.get(key):
            kw.append("%s=%s" % (key, _fmt_tuple(extra[key])))
    if extra.get("gate"):
        kw.append("gate=%s" % _fmt_dict(extra["gate"]))
    if extra.get("hobby"):
        kw.append("hobby=%s" % _fmt_tuple(extra["hobby"]))
    if extra.get("affinity"):
        kw.append("affinity=%s" % _fmt_tuple(extra["affinity"]))
    if extra.get("note"):
        kw.append("note=%r" % extra["note"])

    lines = [
        "    _mk(%r, %r, %r, %d, %d," % (cid, name, rarity, lo, hi),
        "        %r," % text,
        "        %s," % _fmt_dict(effects),
    ]
    lines.append(("        " + ", ".join(kw) + "),") if kw else "    ),")
    return "\n".join(lines)


PROLOGUE = '''"""行动卡：一学期能做的事。

**这个文件由 tools/gen_actions.py 生成，不要手改。**
改内容请改那个脚本里的表，然后跑 `python tools/gen_actions.py`。

设计要点（来自玩家反馈）：
  * 选项粒度要**粗** —— 「娱乐」「休息」「社交」这种说法，
    不要拆成一堆细碎的具体活动。
  * 一个学期十几张卡就够，玩家每学期只挑 3 个。
  * 竞赛不写具体比赛名，只有大类（科研类 / 工程类 / 综合类…），
    阶梯卡由 contests.STAGE_CARDS 自动展开。
  * 单卡效果总和 <= 6，避免某个属性数值爆炸。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config as C
from . import contests as _contests


@dataclass(frozen=True)
class ActionCard:
    id: str
    name: str
    text: str
    rarity: str
    sem_lo: int
    sem_hi: int
    effects: dict
    resources: dict
    flags: tuple
    hobby: tuple | None
    majors: tuple
    is_flex: bool
    tags: tuple
    track: str
    attribute_gate: dict
    start_affinity: tuple
    contest_id: str
    contest_tier: str
    note: str
    # 竞赛卡的属性权重。普通卡为空 —— 它们的 effects 值就是点数。
    strengths: dict


def _mk(cid, name, rarity, lo, hi, text, effects, *, major="", tags=(),
        flags=(), gate=None, hobby=None, affinity=(), note="",
        contest_id="", contest_tier="", resources=None, track="",
        strengths=None):
    """构造一张卡。专业专属卡传 major，竞赛阶梯卡传 contest_id + strengths。"""
    return ActionCard(
        id=cid, name=name, text=text, rarity=rarity,
        sem_lo=lo, sem_hi=hi,
        effects=dict(effects), resources=dict(resources or {}),
        flags=tuple(flags), hobby=hobby,
        majors=(major,) if major else (), is_flex=False,
        tags=tuple(tags), track=track,
        attribute_gate=dict(gate or {}),
        start_affinity=tuple(affinity),
        contest_id=contest_id, contest_tier=contest_tier,
        note=note,
        strengths=dict(strengths or {}),
    )


_TIER_RARITY = {"school": "common", "prov": "rare",
                "national": "epic", "intl": "epic"}

_TIER_TEXT = {
    "school": "在校内选拔里过一轮，先把作品和答辩都磨到能看。",
    "prov": "代表学校去打省赛，对手里开始出现真正的强队。",
    "national": "进国赛，要交完整材料并现场答辩，评审问得很细。",
    "intl": "打进国际赛，对手和评委都换了一批，标准也更高。",
}


def _build_contest_cards():
    """按 contests.STAGE_CARDS 展开竞赛阶梯卡。

    竞赛只写大类，所以卡名就是「科研类竞赛・省赛」这种。
    实际得分在结算时按 strengths 权重分配。
    """
    cards = []
    for contest in _contests.CONTEST_LIST:
        for tier in contest.tiers:
            cards.append(_mk(
                _contests.stage_card_id(contest.id, tier),
                "%s・%s" % (contest.name, C.CONTEST_TIER_NAMES[tier]),
                _TIER_RARITY[tier],
                C.CONTEST_TIER_EARLIEST[tier], C.TOTAL_SEMESTERS,
                _TIER_TEXT[tier],
                {},
                tags=("contest",),
                contest_id=contest.id,
                contest_tier=tier,
                note=contest.note if tier == "school" else "",
                # **必须传**：结算时按这个权重分配属性点。
                # 不传的话 effects.attr_gain 会回落到 {"portfolio": 1.0}，
                # 于是所有竞赛都只加作品分（玩家反馈：
                # "打比赛只加作品分比较不真实"）。
                strengths=contest.strengths,
            ))
    return tuple(cards)


'''

EPILOGUE = '''

CONTEST_CARDS = _build_contest_cards()
ALL_CARDS = GENERAL_CARDS + MAJOR_CARDS + CONTEST_CARDS
CARDS = {card.id: card for card in ALL_CARDS}


def get(card_id):
    return CARDS[card_id]


def contest_cards():
    return list(CONTEST_CARDS)


def major_cards(major_id):
    return [c for c in MAJOR_CARDS if major_id in c.majors]


def for_major(major_id):
    """该专业能看见的卡：通用 + 本专业专属 + 竞赛阶梯卡（按大类过滤）。"""
    visible = {c.id for c in _contests.for_major(major_id)}
    out = []
    for card in ALL_CARDS:
        if card.contest_id:
            if card.contest_id in visible:
                out.append(card)
        elif not card.majors or major_id in card.majors:
            out.append(card)
    return out


def cards_for_semester(sem, major_id):
    return [c for c in for_major(major_id) if c.sem_lo <= sem <= c.sem_hi]


def card_is_contest(card):
    return bool(card.contest_id)


def rest_cards():
    """保底卡：永远可选、收益最低，用来兜底。"""
    return [c for c in ALL_CARDS if c.rarity == "safe"]


def semester_coverage(major_id):
    """该专业每个学期有多少张专属卡（不含竞赛卡）。"""
    return {
        sem: sum(
            1 for c in MAJOR_CARDS
            if major_id in c.majors and c.sem_lo <= sem <= c.sem_hi
        )
        for sem in range(1, C.TOTAL_SEMESTERS + 1)
    }


def _validate():
    problems = []

    ids = [c.id for c in ALL_CARDS]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        problems.append("重复的卡 id: %s" % dupes[:5])

    for c in ALL_CARDS:
        if c.rarity not in C.RARITY_MULT:
            problems.append("%s 品质非法" % c.id)
        if not (1 <= c.sem_lo <= c.sem_hi <= C.TOTAL_SEMESTERS):
            problems.append("%s 学期区间越界 (%d-%d)" % (c.id, c.sem_lo, c.sem_hi))
        if not c.name or not c.text:
            problems.append("%s 文案有空字段" % c.id)
        if len(c.name) > 14:
            problems.append("%s 卡名过长：%s" % (c.id, c.name))
        for k in c.effects:
            if k not in C.ATTRS:
                problems.append("%s 含非法属性 %s" % (c.id, k))
        total = sum(c.effects.values())
        if total > 6:
            problems.append("%s 效果总和 %d 超过上限 6" % (c.id, total))
        for k, v in c.attribute_gate.items():
            if k not in C.ATTRS:
                problems.append("%s 门槛属性非法 %s" % (c.id, k))
            if not (2 <= v <= 16):
                problems.append("%s 门槛 %s=%d 超出 2-16" % (c.id, k, v))
        if c.hobby:
            key, xp = c.hobby
            if key not in C.HOBBY_KEYS:
                problems.append("%s 引用了不存在的爱好 %s" % (c.id, key))
            if xp <= 0:
                problems.append("%s 的爱好经验必须为正" % c.id)

    for sem in range(1, C.TOTAL_SEMESTERS + 1):
        n = sum(1 for c in GENERAL_CARDS if c.sem_lo <= sem <= c.sem_hi)
        if n < 6:
            problems.append("第 %d 学期只有 %d 张通用卡" % (sem, n))

    for major_id in ("cs", "mech", "civil", "sci", "biz", "ocean", "med", "hum"):
        for sem, n in semester_coverage(major_id).items():
            if n < 2:
                problems.append("%s 第 %d 学期只有 %d 张专属卡" % (major_id, sem, n))

    if problems:
        raise ValueError("actions.py 内容有问题：\\n  - " + "\\n  - ".join(problems))


_validate()
'''


def main() -> int:
    out = [PROLOGUE]

    out.append("# ==================================================== 通用卡\n")
    out.append("GENERAL_CARDS = (\n")
    for row in GENERAL:
        out.append(_render(*row[:5], "", row[5], row[6], row[7], row[8]))
    out.append("\n)\n")

    out.append("\n\n# ==================================================== 专业专属卡\n")
    out.append("MAJOR_CARDS = (\n")
    for row in MAJOR:
        out.append(_render(*row[:5], row[5], row[6], row[7], row[8], row[9]))
    out.append("\n)\n")

    out.append(EPILOGUE)

    text = "".join(out)
    OUT.write_text(text, encoding="utf-8")
    print("wrote %s (%d bytes)" % (OUT.name, len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
