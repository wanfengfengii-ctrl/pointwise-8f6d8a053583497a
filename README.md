# 澄湾巡检资料中心

白班测绘员固定路网修订，制图员提交纸幅布局，交班员签出固定包。夜班隔离库接纳实交材料，从包中核算合法最短路线并固定核查单。次日更正追加新修订，资料员凭两个原单号核对结果。

需要 Python 3.11 和标准库。请从项目根目录执行。

```sh
python3 -B check_project.py
python3 -B demo.py
```

控制台物化时提供 `check_project.py`。演示从 `samples/` 读取声明，在临时目录建立源库和隔离库，完成两次交班、断源复核、重开及原单对照。初版禁 `a → b → c`，`X` 到 `T` 经 `h → d → b → c`，代价 5。更正后经 `a → b → c`，代价 4。单幅和多幅的初版结果一致。

## Python 入口

- `survey.revision_store.RevisionStore(path)` 保存源修订，`survey.revisions.save_revision(store, junctions, roads, restrictions)` 追加固定修订并返回修订号。`load_revision(store, revision_id)` 读取该号。
- `exchange.catalog.BundleCatalog(path)` 保存发布件或隔离接纳件。`exchange.publish.publish(revisions, catalog, revision_id, plan)` 返回 `(bundle_id, wire)`。`exchange.imports.import_bundle(catalog, wire)` 核验并接纳 `bytes`，返回包号。`find_published` 和 `find_accepted` 按号返回实件或 `None`。
- `review.record_store.RecordStore(path)` 保存核查单。`review.issue.issue(catalog, records, ReviewRequest(bundle_id, start, end))` 返回固定核查单。`review.retrieve.retrieve(records, record_id)` 返回原单或 `None`。`review.compare.compare(records, before_id, after_id)` 返回两单及可达性、原路段序列和代价变化。

先对各存储对象调用 `initialize()`。源端的修订和发布目录可共用一个 SQLite 文件，隔离端的接纳目录与核查单也可共用一个文件。业务调用按次管理连接和写入事务。提交失败传播 SQLite 错误并回滚本次写入。未知修订、未知包和对照中的未知单号引发 `KeyError`。非法声明、包或端点及不同端点对的对照引发 `ValueError`。

## 数据口径

`Junction` 按名称标识实路口。`Road` 指定标识、起终点和正整数代价，反向通行使用独立路段号。`Restriction` 仅禁止连续完成其声明的三个有向路段。`LayoutPlan` 声明幅面、人工缝点和按路段从 0 编号的片段。片段名在其幅内唯一。缝点键由原路段和缝名组成，坐标使用整数纸面单位。片段代价使用整数分摊值，并逐路精确还原正整数原价。代价以整数单位累计和比较，交换件及持久记录用十六进制文本保全整数原值。

交换件为含 `manifest` 和 `payload` 的 JSON 对象。清单绑定包号、修订、布局和载荷摘要。载荷保存实路口、有向路段、幅面、缝点、完整片段与规则对应。发布时核对该修订的规则覆盖，接纳时核对实件内部关系。接纳按规范内容判断重复件，已有包号的绑定保持固定。

寻路用完成的原路段推进规则。人工缝点只能接续所属链，同坐标的缝点仍是各自的身份。路线按总代价、原路段号序列排序。同一实路口到自身返回空序列和 0。合法端点间没有可走路线时签出不可达，路线与代价均为 `None`。
