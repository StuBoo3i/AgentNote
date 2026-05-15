这 4 个新增失败不是同一个原因：

task_199：计划阶段把 “Riverside-related school districts” 扩大成了 district_name LIKE '%Riverside%' OR county_name LIKE '%Riverside%'，多返回 60 行。
task_249：题意中 “up votes” 应该取 db_users_users.upvotes，新 run 错取了 json_posts.score。
task_303：计算逻辑正确，但最终把 52.17391304347826 四舍五入成 52.17。
task_415：Doc structuring 误把 doc/races.md 抽成医学 lab schema 的空表 doc_races，导致执行阶段围绕空 doc 表反复空转，最终没提交答案。
Task 199

题目：列出 Riverside-related school districts 中 SAT math 平均分超过 400 的学校名和 funding type。

旧 run 正确 SQL：

WHERE T1.district_name LIKE '%Riverside%'
  AND T2.AvgScrMath > 400
返回 6 行，和 gold 一致。

新 run 第 1 步先查：

SELECT DISTINCT district_name
FROM csv_frpm
WHERE district_name LIKE '%Riverside%' OR county_name LIKE '%Riverside%'
第 7 步最终也用了：

WHERE (T1.district_name LIKE '%Riverside%' OR T1.county_name LIKE '%Riverside%')
  AND T2.avgscrmath > 400
这把整个 Riverside County 的学校都纳入了，而不是只要 district name 含 Riverside 的 school district，结果从 6 行膨胀到 60 行。

根因：plan 阶段过度扩展了 “Riverside-related school districts”。题目说的是 school districts，过滤应落在 district_name，新 plan 擅自加入 county_name。

项目建议：

context_pack.py 对 “X-related school districts” 这类短语生成 filter contract：优先 district_name LIKE '%X%'，不要自动扩大到 county_name。
langgraph_agent.py answer validation 增加异常行数膨胀 warning：同一任务中如果候选 SQL 从 6 行变成 60 行，且新增条件是 OR county_name，应提示“过滤范围被扩大”。
Task 249

题目：What is the average of the up votes and the average user age for users creating more than 10 posts?

gold 和旧 run 都是：

AVG(u.upvotes), AVG(u.age)
FROM db_users_users u
JOIN (
  SELECT owneruserid
  FROM json_posts
  GROUP BY owneruserid
  HAVING COUNT(*) > 10
) p ON u.id = p.owneruserid
旧结果：

182.2832618025751, 34.083333333333336
新 run 第 2 步用了：

SELECT AVG(p.Score) as avg_up_votes, AVG(u.Age) as avg_user_age
FROM db_users_users u
INNER JOIN json_posts p ON u.Id = p.OwnerUserId
WHERE u.Id IN (
  SELECT OwnerUserId
  FROM json_posts
  GROUP BY OwnerUserId
  HAVING COUNT(*) > 10
)
结果变成：

3.293011975140215, 35.26408063822672
这里错在两点：

up votes 被理解成 post score，即 json_posts.score。
join 到 posts 后对每个 post 行求平均，导致 u.age 也被按 post 数重复加权，变成 35.264，而不是对用户集合求平均。
知识文件明确写了：

Users: UpVotes/DownVotes: Count of upvotes and downvotes received by the user.
Posts: Score: Rating score of the post.
根因：新 plan 把 “users creating more than 10 posts” 里的 posts 当成了平均对象，实际 posts 只用于筛选用户集合；最终平均对象仍是 users 表字段。

项目建议：

context_pack.py 增加聚合对象识别：average of X and average user age for users ... 中，X 和 user age 同属 user-level metric，posts 子句只生成 filter subquery。
对 up votes / down votes 建立低风险 schema grounding：若 users 表有 upvotes，posts 表只有 score，优先 users.upvotes，禁止把 posts.score 改名为 up votes。
validation 增加 grain 检查：如果最终平均的是 user-level 字段，但 SQL join 到 detail posts 表后直接 AVG(u.age)，应提示可能发生一对多重复加权。
Task 303

题目：European Grand Prix 中 hosted in Germany 的百分比。

新旧 run 的计数都正确：

total_european_gp = 23
germany_count = 12
正确值：

12 / 23 * 100 = 52.17391304347826
旧 run 输出完整精度：

52.17391304347826
新 run 第 4 步 Python 明确做了四舍五入：

percentage = (12 / 23) * 100
print(f"{percentage:.2f}")
最终输出：

52.17
根因：不是查表错，也不是公式错，是最终格式化错。题目没有要求保留两位小数，benchmark gold 使用完整浮点表达式结果，当前 validation 没有拦截“无要求的 rounding”。

项目建议：

langgraph_agent.py prompt 增加规则：除非题目明确要求 round / decimal places，否则不要格式化或四舍五入数值。
answer validation 增加 warning：如果最近 SQL/Python 有更高精度数值，但 answer 使用更短小数，提示“possible unintended rounding”。
对 percentage / ratio contract 增加 precision_policy: preserve_full_precision_unless_requested。
Task 415

题目：2009 Singapore Grand Prix champion 的 constructor reference name 和 website。

旧 run 虽然走了很多步，但关键链路正确：

读 doc/races.md 找到：
Singapore Grand Prix (Race ID: 14)
查 results.db：
SELECT r.constructorId, r.positionOrder
FROM results r
WHERE r.raceId = 14 AND r.positionOrder = 1
得到 constructorId = 1
读 constructors.json，输出：
mclaren, http://en.wikipedia.org/wiki/McLaren
新 run 的问题从 context pack 就开始了：

doc_schema_hypotheses: [
  {
    "name": "doc_races",
    "source_path": "doc/races.md",
    "entity": "laboratory",
    "columns": ["patient_id", "lab_field", "lab_value", "status_text"]
  }
]
这明显错了。races.md 是 Formula 1 race dossier，却被抽成了医学 laboratory schema。

随后 unified DB 中出现空表：

doc_races(patient_id, lab_field, lab_value, status_text, ...)
rows: []
新 trace 多次查询空表：

SELECT * FROM doc_races LIMIT 5
SELECT * FROM doc_races LIMIT 10
还尝试了不存在的结构：

no such table: csv_races
no such column: T1.year
no such table: races
最终 30 步内没有回到旧 run 的有效路径：直接 read doc/races.md，抽 Race ID: 14，再查 results 和 constructors。

根因：

Doc schema planner 把 Formula 1 races.md 误分类成 lab 文档。
空抽取表被写入 unified DB 后，agent 误以为 doc 已结构化可查。
doc_extraction_requirements 被加入 filters_must_apply，强化了错误方向。
缺少 fallback：doc table 为空时，应回退到 read_doc / regex evidence，而不是继续查空表。
项目建议：

doc_structuring.py 修正 schema discovery：races.md + Formula 1 knowledge + question 中 Grand Prix/raceId/year 应生成 race schema：
doc_races(race_id, race_name, year, url, evidence)
不能落到 medical/laboratory schema。
unified_db.py / doc import 增加空表降权：doc extracted table row_count=0 时，不应作为高可信 unified table 暴露给 planning。
context_pack.py 不要把所有 doc requirements 直接塞进 filters_must_apply；只有抽取 schema 和题目字段匹配、且 coverage > 0 时才强制。
langgraph_agent.py 增加 doc fallback：连续两次查询 doc extracted table 为空后，自动提示改用 read_doc 读取原文证据。
共性问题

这批新增失败说明近期优化引入了几个系统性副作用：

Context Pack/plan 更强后，错误先验也会更强。
task_415 最明显，错误 doc schema 一旦进入 prompt 和 unified DB，模型会围绕错误结构空转。

缺少 answer grain/source/precision 的硬约束。
task_249 是 grain 错，task_303 是 precision 错，task_199 是 filter scope 错。

validation 仍偏“表形状校验”，不足以发现语义层错误。
这些任务的输出列数大多没问题，但 value source、过滤范围、聚合粒度或数值精度错了。