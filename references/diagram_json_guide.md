# 声明式图表 JSON 规范 (`scripts/diagram_dsl.py`)

支持 4 种图表类型：`layers`（架构分层图）、`flowchart`（流程图/上下文图）、`sequence`（时序图）、`class`（UML 类图）。输入可以是单个对象或对象数组，脚本会按每个对象的 `id` 输出 `<id>.html`，再由 `snap_diagrams.cjs` 截图生成 `<id>.png`。

---

## 1. `flowchart`（流程图 / 上下文图）

```json
{
  "id": "fig3_1_backbone",
  "type": "flowchart",
  "title": "图 3-1 系统运行主干流程图",
  "width": 980,
  "height": 540,
  "groups": [
    { "x": 30, "y": 50, "w": 920, "h": 140, "label": "阶段一", "fill": "#F8FAFC", "stroke": "#2E74B5" }
  ],
  "nodes": [
    { "id": "start", "kind": "start", "x": 350, "y": 60, "w": 280, "h": 50, "lines": ["开始: EntryAbility.onCreate"] },
    { "id": "chk", "kind": "decision", "cx": 490, "cy": 180, "w": 220, "h": 64, "lines": ["校验是否通过?"] },
    { "id": "ok", "kind": "process", "x": 350, "y": 250, "w": 280, "h": 54, "lines": ["启动业务服务", "进入稳态调度"] },
    { "id": "err", "kind": "error", "x": 690, "y": 152, "w": 240, "h": 56, "lines": ["记录告警并中止"] }
  ],
  "edges": [
    { "from": "start", "fromSide": "bottom", "to": "chk", "toSide": "top" },
    { "from": "chk", "fromSide": "bottom", "to": "ok", "toSide": "top", "label": "通过", "color": "#059669" },
    { "from": "chk", "fromSide": "right", "to": "err", "toSide": "left", "label": "失败", "color": "#C62828" }
  ]
}
```
> `kind` 支持：`start` / `end` / `process` / `decision` / `warn` / `error` / `muted` / `purple` / `green`。

---

## 2. `sequence`（时序图）

```json
{
  "id": "fig3_2_seq",
  "type": "sequence",
  "title": "图 3-2 建连与断链重连时序图",
  "width": 1040,
  "height": 520,
  "participants": [
    { "id": "svc", "label": "Service" },
    { "id": "mgr", "label": "ConnectManager" },
    { "id": "sdk", "label": "ProtocolStack" }
  ],
  "frames": [
    { "x": 50, "y": 240, "w": 940, "h": 150, "label": "alt 异常断链处理", "fill": "#FFFDF7", "stroke": "#D97706" }
  ],
  "messages": [
    { "kind": "note", "x": 60, "x2": 980, "y": 106, "label": "冷启动初始化建连阶段" },
    { "from": "svc", "to": "mgr", "y": 155, "label": "1. start()" },
    { "from": "mgr", "to": "sdk", "y": 190, "label": "2. connect()", "color": "#2E74B5" },
    { "from": "sdk", "to": "mgr", "y": 222, "label": "3. onConnected()", "dashed": true, "color": "#059669" }
  ]
}
```

---

## 3. `class`（UML 类图）

```json
{
  "id": "fig3_3_cls",
  "type": "class",
  "title": "图 3-3 核心类与接口结构图",
  "width": 1060,
  "height": 460,
  "classes": [
    {
      "id": "mgr", "name": "SessionManager", "stereotype": "«Singleton»", "role": "singleton",
      "x": 340, "y": 55, "w": 360,
      "attrs": ["-state: SessionState", "-timeoutMs: number = 15000"],
      "methods": ["+start(): Promise<Result>", "+stop(): Promise<void>"]
    },
    {
      "id": "cb", "name": "SessionListener", "stereotype": "«interface»", "role": "interface",
      "x": 380, "y": 280, "w": 280,
      "methods": ["+onStateChanged(s): void"]
    }
  ],
  "relations": [
    { "from": "mgr", "fromSide": "bottom", "to": "cb", "toSide": "top", "kind": "notify", "label": "回调通知" }
  ]
}
```
> `role` 支持 `singleton` / `facade` / `core` / `interface` / `constants` / `default`；`kind` 支持 `assoc` / `depend` / `realize` / `inherit` / `notify`。脚本会自动根据最长文本行撑宽卡片，防止签名截断。

---

## 4. `layers`（四层架构与依赖图）

```json
{
  "id": "fig2_2_layers",
  "type": "layers",
  "title": "图 2-2 系统分层与模块依赖图",
  "width": 980,
  "height": 500,
  "layers": [
    {
      "y": 55, "h": 92, "title": "L3 视图层 (entry)", "badge": "MD-03", "fill": "#EFF6FF", "stroke": "#2E74B5",
      "items": [["MainViewModel", "状态聚合"], ["MainPage", "ArkUI 局部刷新"]]
    },
    {
      "y": 175, "h": 92, "title": "L2 业务层 (service)", "badge": "MD-02", "fill": "#ECFDF5", "stroke": "#059669",
      "items": [["CoreService", "业务门面"], ["StateStore", "状态管理"]]
    }
  ],
  "arrows": [
    { "points": [[240, 147], [240, 175]], "label": "同步调用", "color": "#2E74B5" },
    { "points": [[650, 175], [650, 147]], "label": "异步事件", "color": "#059669", "dash": "5,3" }
  ],
  "footer": "依赖约束：严禁下层反向引用上层，跨层异步事件统一经 EventBus 广播。"
}
```
