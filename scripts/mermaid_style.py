"""Shared Mermaid theme (init lines), classDefs and helpers for generating GitHub-native diagrams.

Usage: from mermaid_style import flow, seq, other, L. Copy the init line of an existing diagram when editing by hand."""
# shared mermaid helpers
INIT_FLOW='%%{init: {"theme": "base", "fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "themeVariables": {"fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "fontSize": "14px", "primaryColor": "#F4F6F9", "primaryTextColor": "#1B2733", "primaryBorderColor": "#5B6B82", "lineColor": "#5B6B82", "clusterBkg": "#FAFBFC", "clusterBorder": "#9AA5B1", "edgeLabelBackground": "#FFFFFF"}, "flowchart": {"curve": "basis", "nodeSpacing": 40, "rankSpacing": 55}}}%%'
INIT_SEQ='%%{init: {"theme": "base", "fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "themeVariables": {"fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "fontSize": "14px", "actorBkg": "#1168BD", "actorBorder": "#0B4884", "actorTextColor": "#FFFFFF", "actorLineColor": "#9AA5B1", "signalColor": "#1B2733", "signalTextColor": "#1B2733", "labelBoxBkgColor": "#E8EEF6", "labelBoxBorderColor": "#5B6B82", "labelTextColor": "#1B2733", "loopTextColor": "#1B2733", "noteBkgColor": "#FFF8E1", "noteBorderColor": "#C77700", "noteTextColor": "#1B2733", "activationBkgColor": "#E8EEF6", "activationBorderColor": "#1168BD", "sequenceNumberColor": "#FFFFFF"}, "sequence": {"mirrorActors": false, "showSequenceNumbers": true}}}%%'
INIT_BASE='%%{init: {"theme": "base", "fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "themeVariables": {"fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "fontSize": "14px", "primaryColor": "#E8EEF6", "primaryTextColor": "#1B2733", "primaryBorderColor": "#1168BD", "lineColor": "#5B6B82", "secondaryColor": "#F4F6F9", "tertiaryColor": "#FFFFFF"}}}%%'
INIT_GANTT='%%{init: {"theme": "base", "fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "themeVariables": {"fontFamily": "Helvetica, Arial, DejaVu Sans, sans-serif", "fontSize": "13px", "primaryColor": "#1168BD", "primaryBorderColor": "#0B4884", "primaryTextColor": "#1B2733", "sectionBkgColor": "#F4F6F9", "altSectionBkgColor": "#FFFFFF", "sectionBkgColor2": "#E8EEF6", "taskBkgColor": "#1168BD", "taskBorderColor": "#0B4884", "taskTextColor": "#FFFFFF", "taskTextOutsideColor": "#1B2733", "doneTaskBkgColor": "#9AA5B1", "critBkgColor": "#C77700", "todayLineColor": "#C77700", "gridColor": "#DDE3EA"}, "gantt": {"barHeight": 22, "fontSize": 13, "leftPadding": 230}}}%%'
CLASSDEFS='''  classDef person fill:#08427B,stroke:#052E56,color:#FFFFFF
  classDef app fill:#1168BD,stroke:#0B4884,color:#FFFFFF
  classDef agent fill:#2E7D7A,stroke:#1F5654,color:#FFFFFF
  classDef data fill:#F4F6F9,stroke:#5B6B82,color:#1B2733
  classDef external fill:#8A94A3,stroke:#5B6B82,color:#FFFFFF
  classDef security fill:#FFF4E5,stroke:#C77700,color:#1B2733
  classDef infra fill:#E8EEF6,stroke:#1168BD,color:#1B2733'''
SG='fill:#FAFBFC,stroke:#9AA5B1,stroke-width:1px,stroke-dasharray:5 3,color:#1B2733'
def L(name,kind): return f'"`**{name}**\n    _{kind}_`"'
def flow(did,direction,body,subgraphs=()):
    st="\n".join(f"  style {s} {SG}" for s in subgraphs)
    return f"```mermaid\n{INIT_FLOW}\n%% diagram: {did}\nflowchart {direction}\n{body.rstrip()}\n{CLASSDEFS}\n{st}\n```".replace("\n\n```","\n```")
def seq(did,body): return f"```mermaid\n{INIT_SEQ}\n%% diagram: {did}\nsequenceDiagram\n  autonumber\n{body.rstrip()}\n```"
def other(did,kind,body,init=INIT_BASE): return f"```mermaid\n{init}\n%% diagram: {did}\n{kind}\n{body.rstrip()}\n```"
LEGEND='''> **Diagram legend:**
> - Dark blue: person.
> - Blue: Databricks container.
> - Teal: agent component.
> - Light grey: data store.
> - Grey: external system.
> - Amber: security or network control.
> - Pale blue: AWS infrastructure.
> - Dashed boxes: trust or deployment boundaries.'''
