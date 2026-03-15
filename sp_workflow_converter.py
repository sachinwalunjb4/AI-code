#!/usr/bin/env python3
"""
SharePoint 2013 Designer Workflow XML to HTML Converter
Converts SP 2013 .xoml / .xml workflow definitions into a SharePoint Designer-like HTML viewer.

Usage:
    python sp_workflow_converter.py <workflow.xml>
    python sp_workflow_converter.py sample_workflow.xml
"""

import sys
import os
import re
import json
import html
import datetime
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Activity type metadata (display name, color class, icon, description)
# ---------------------------------------------------------------------------
ACTIVITY_META = {
    # Logging
    "logtohistorylistactivity": {
        "label": "Log to History List",
        "color": "act-log",
        "icon": "&#128196;",
        "category": "Utility",
    },
    # Field operations
    "setfieldactivity": {
        "label": "Set Field Value",
        "color": "act-field",
        "icon": "&#9998;",
        "category": "List Actions",
    },
    "updatelistitemactivity": {
        "label": "Update List Item",
        "color": "act-field",
        "icon": "&#128260;",
        "category": "List Actions",
    },
    # Email
    "sendemailactivity": {
        "label": "Send an Email",
        "color": "act-email",
        "icon": "&#9993;",
        "category": "Email",
    },
    # Tasks
    "createtaskwithcontenttypeactivity": {
        "label": "Create Task",
        "color": "act-task",
        "icon": "&#9745;",
        "category": "Task Actions",
    },
    "createtaskactivity": {
        "label": "Create Task",
        "color": "act-task",
        "icon": "&#9745;",
        "category": "Task Actions",
    },
    "ontaskchanged": {
        "label": "Wait for Task",
        "color": "act-wait",
        "icon": "&#9203;",
        "category": "Task Actions",
    },
    # Conditions
    "ifelseactivity": {
        "label": "If/Else Condition",
        "color": "act-condition",
        "icon": "&#10070;",
        "category": "Conditions",
    },
    "ifelsebranchactivity": {
        "label": "Condition Branch",
        "color": "act-branch",
        "icon": "&#10145;",
        "category": "Conditions",
    },
    # Parallel / Sequence
    "parallelactivity": {
        "label": "Parallel Block",
        "color": "act-parallel",
        "icon": "&#9776;",
        "category": "Flow Control",
    },
    "sequenceactivity": {
        "label": "Sequence",
        "color": "act-sequence",
        "icon": "&#9654;",
        "category": "Flow Control",
    },
    # Date
    "builddateactivity": {
        "label": "Calculate Date",
        "color": "act-calc",
        "icon": "&#128197;",
        "category": "Utility",
    },
    # Wait / field change
    "onfieldchange": {
        "label": "Wait for Field Change",
        "color": "act-wait",
        "icon": "&#9203;",
        "category": "Wait",
    },
    # Aliases for sp: namespace short names (no "activity" suffix)
    "logtohistorylist": {
        "label": "Log to History List",
        "color": "act-log",
        "icon": "&#128196;",
        "category": "Utility",
    },
    "sendemail": {
        "label": "Send an Email",
        "color": "act-email",
        "icon": "&#9993;",
        "category": "Email",
    },
    "setfield": {
        "label": "Set Field Value",
        "color": "act-field",
        "icon": "&#9998;",
        "category": "List Actions",
    },
    "createtask": {
        "label": "Create Task",
        "color": "act-task",
        "icon": "&#9745;",
        "category": "Task Actions",
    },
    "completetask": {
        "label": "Complete Task",
        "color": "act-task",
        "icon": "&#9989;",
        "category": "Task Actions",
    },
    # Workflow control
    "onworkflowactivated": {
        "label": "On Workflow Activated",
        "color": "act-default",
        "icon": "&#9654;",
        "category": "Workflow",
    },
    "setworkflowvariable": {
        "label": "Set Workflow Variable",
        "color": "act-field",
        "icon": "&#128221;",
        "category": "Variables",
    },
    "delayfor": {
        "label": "Pause / Delay",
        "color": "act-wait",
        "icon": "&#9203;",
        "category": "Wait",
    },
    # Loop
    "whileactivity": {
        "label": "Loop (While)",
        "color": "act-condition",
        "icon": "&#8635;",
        "category": "Flow Control",
    },
    # Misc
    "default": {
        "label": "Workflow Action",
        "color": "act-default",
        "icon": "&#9654;",
        "category": "Action",
    },
}


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------

def strip_ns(tag: str) -> str:
    """Remove XML namespace from a tag name and return lowercase."""
    if "}" in tag:
        return tag.split("}", 1)[1].lower()
    return tag.lower()


def get_meta(tag_local: str) -> dict:
    """Return display metadata for an activity type."""
    return ACTIVITY_META.get(tag_local, ACTIVITY_META["default"])


def clean_value(val: str) -> str:
    """Make a raw attribute value human-readable."""
    if not val:
        return ""
    # Remove ActivityBind expressions but keep the Path part
    m = re.search(r"Path=([^,}]+)", val)
    if m:
        return m.group(1).strip()
    # Remove {workflow:...} wrappers
    val = re.sub(r"\{workflow:(\w+)\}", r"[\1]", val)
    return val.strip()


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def collect_namespaces(xml_path: str) -> dict:
    """Collect all namespace prefix->URI mappings in the file."""
    ns_map = {}
    try:
        for event, elem in ET.iterparse(xml_path, events=["start-ns"]):
            prefix, uri = elem
            ns_map[prefix] = uri
    except ET.ParseError:
        pass
    return ns_map


def parse_attributes(elem: ET.Element) -> dict:
    """Return a sanitised dict of element attributes (all keys lowercased)."""
    attrs = {}
    for key, val in elem.attrib.items():
        if "}" in key:
            clean_key = strip_ns(key)  # already lowercased by strip_ns
        else:
            clean_key = key.split(":")[-1].lower()
        attrs[clean_key] = val
    return attrs


def parse_element(elem: ET.Element, depth: int = 0) -> dict:
    """Recursively parse a workflow element into a plain dict."""
    tag_local = strip_ns(elem.tag)
    attrs = parse_attributes(elem)
    display_name = attrs.get("displayname") or attrs.get("name") or tag_local
    meta = get_meta(tag_local)

    node = {
        "tag": tag_local,
        "display_name": display_name,
        "meta": meta,
        "attrs": attrs,
        "depth": depth,
        "children": [],
    }

    # Collect field update sub-elements
    field_updates = []
    for child in elem:
        child_local = strip_ns(child.tag)
        if child_local in ("updatelistitemfieldvalue",):
            child_attrs = parse_attributes(child)
            field_updates.append({
                "field": child_attrs.get("fieldname", ""),
                "value": child_attrs.get("value", ""),
            })
        elif child_local.endswith(".fields") or child_local.endswith(".metadata") or child_local.endswith(".variables"):
            # Recurse into metadata/variable containers
            for sub in child:
                sub_local = strip_ns(sub.tag)
                if sub_local == "updatelistitemfieldvalue":
                    sub_attrs = parse_attributes(sub)
                    field_updates.append({
                        "field": sub_attrs.get("fieldname", ""),
                        "value": sub_attrs.get("value", ""),
                    })
        elif child_local not in (
            "rootactivity.metadata",
            "rootactivity.variables",
            "sequentialworkflowactivity.variables",
            "workflowinfo",
            "workflowproperty",
            "variable",
            "codecondition",
            "whileactivity.condition",
            "ifelsebranchactivity.condition",
        ):
            parsed_child = parse_element(child, depth + 1)
            if parsed_child:
                node["children"].append(parsed_child)

    node["field_updates"] = field_updates
    return node


def extract_workflow_meta(root: ET.Element) -> dict:
    """Extract workflow-level metadata from <WorkflowInfo> block."""
    meta = {
        "name": "Unnamed Workflow",
        "description": "",
        "author": "",
        "created": "",
        "modified": "",
        "list_url": "",
        "start_manually": "false",
        "start_on_create": "false",
        "start_on_change": "false",
        "variables": [],
    }

    for elem in root.iter():
        local = strip_ns(elem.tag)
        if local == "workflowproperty":
            attrs = parse_attributes(elem)
            name_key = attrs.get("name", "").lower()
            value = attrs.get("value", "")
            if name_key == "workflowname":
                meta["name"] = value
            elif name_key == "workflowdescription":
                meta["description"] = value
            elif name_key == "author":
                meta["author"] = value
            elif name_key == "created":
                meta["created"] = value
            elif name_key == "modified":
                meta["modified"] = value
            elif name_key == "listurl":
                meta["list_url"] = value
            elif name_key == "startmanually":
                meta["start_manually"] = value
            elif name_key == "startoncreate":
                meta["start_on_create"] = value
            elif name_key == "startonchange":
                meta["start_on_change"] = value
        elif local == "variable":
            attrs = parse_attributes(elem)
            meta["variables"].append({
                "name": attrs.get("name", ""),
                "type": attrs.get("type", "").split(".")[-1],
                "default": attrs.get("default", ""),
            })

    return meta


def is_container(tag_local: str) -> bool:
    """Return True if an activity is a container (sequence/parallel/branch)."""
    return tag_local in (
        "sequenceactivity",
        "parallelactivity",
        "ifelseactivity",
        "ifelsebranchactivity",
        "rootactivity",
        "sequentialworkflowactivity",
        "whileactivity",
    )


# ---------------------------------------------------------------------------
# Step flattening (for numbered sidebar + main view)
# ---------------------------------------------------------------------------

STEP_COUNTER = [0]


def flatten_steps(node: dict, steps: list, parent_id: str = "root"):
    """Recursively flatten the activity tree, assigning step numbers."""
    tag = node["tag"]
    if tag in ("rootactivity", "sequentialworkflowactivity"):
        for child in node["children"]:
            flatten_steps(child, steps, parent_id)
        return

    if tag == "sequenceactivity" and node["depth"] == 1:
        # Top-level sequence — recurse without adding itself
        for child in node["children"]:
            flatten_steps(child, steps, parent_id)
        return

    STEP_COUNTER[0] += 1
    step_id = f"step_{STEP_COUNTER[0]}"
    node["step_id"] = step_id
    node["step_number"] = STEP_COUNTER[0]
    steps.append(node)

    for child in node["children"]:
        flatten_steps(child, steps, step_id)


# ---------------------------------------------------------------------------
# HTML generation helpers
# ---------------------------------------------------------------------------

CSS = """
:root {
    --sp-blue-dark:    #003366;
    --sp-blue:         #0072C6;
    --sp-blue-light:   #D0E4F7;
    --sp-blue-hover:   #005A9E;
    --sp-gray-dark:    #3C3C3C;
    --sp-gray:         #767676;
    --sp-gray-light:   #F0F0F0;
    --sp-gray-mid:     #D8D8D8;
    --sp-white:        #FFFFFF;
    --sp-orange:       #E87722;
    --sp-green:        #4CAF50;
    --sp-yellow:       #FFC107;
    --sp-red:          #D32F2F;
    --sp-purple:       #7B1FA2;
    --sidebar-w:       260px;
    --props-w:         300px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
    background: var(--sp-gray-light);
    color: var(--sp-gray-dark);
    overflow: hidden;
    height: 100vh;
}

/* ===== TOP RIBBON / HEADER ===== */
#ribbon {
    background: linear-gradient(180deg, #1a5ba6 0%, var(--sp-blue-dark) 100%);
    color: #fff;
    padding: 0;
    height: 88px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 4px rgba(0,0,0,0.35);
    flex-shrink: 0;
}
#ribbon-top {
    display: flex;
    align-items: center;
    padding: 6px 14px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    height: 40px;
    gap: 10px;
}
#ribbon-logo {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
}
#ribbon-logo span.sp-icon { font-size: 22px; }
#ribbon-subtitle {
    font-size: 11px;
    opacity: 0.75;
    margin-left: auto;
}
#ribbon-bottom {
    display: flex;
    align-items: center;
    padding: 4px 14px;
    gap: 20px;
    flex: 1;
}
.ribbon-btn {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 3px;
    color: #fff;
    padding: 4px 10px;
    font-size: 11px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 5px;
    transition: background 0.15s;
}
.ribbon-btn:hover { background: rgba(255,255,255,0.25); }
#wf-name-ribbon {
    font-size: 16px;
    font-weight: 600;
    margin-left: 10px;
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ===== BREADCRUMB ===== */
#breadcrumb {
    background: #e8f0f8;
    border-bottom: 1px solid var(--sp-gray-mid);
    padding: 5px 14px;
    font-size: 11px;
    color: var(--sp-blue);
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
}
#breadcrumb span { color: var(--sp-gray); }
#breadcrumb a { color: var(--sp-blue); text-decoration: none; }
#breadcrumb a:hover { text-decoration: underline; }

/* ===== MAIN LAYOUT ===== */
#workspace {
    display: flex;
    height: calc(100vh - 88px - 28px);
    overflow: hidden;
}

/* ===== LEFT SIDEBAR (Steps Navigator) ===== */
#sidebar {
    width: var(--sidebar-w);
    background: #1e3a5f;
    color: #cde0f5;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    overflow: hidden;
    border-right: 2px solid #0a2540;
}
#sidebar-header {
    background: #0a2540;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #7fb3e8;
    flex-shrink: 0;
}
#sidebar-search {
    padding: 6px 8px;
    background: #162d4d;
    border-bottom: 1px solid #0a2540;
    flex-shrink: 0;
}
#sidebar-search input {
    width: 100%;
    padding: 4px 8px;
    border: 1px solid #2a4f7a;
    border-radius: 3px;
    background: #0d2035;
    color: #cde0f5;
    font-size: 11px;
    outline: none;
}
#sidebar-search input::placeholder { color: #5a7fa5; }
#step-list {
    overflow-y: auto;
    flex: 1;
    padding: 4px 0;
}
.step-item {
    padding: 6px 10px 6px 14px;
    cursor: pointer;
    border-left: 3px solid transparent;
    transition: background 0.12s, border-color 0.12s;
    display: flex;
    align-items: flex-start;
    gap: 7px;
    font-size: 12px;
    line-height: 1.35;
}
.step-item:hover { background: #2a4f7a; border-left-color: #5ba3e0; }
.step-item.active { background: #1a6bb5; border-left-color: #7fc0ff; color: #fff; }
.step-num {
    min-width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgba(255,255,255,0.12);
    font-size: 10px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
}
.step-item.active .step-num { background: rgba(255,255,255,0.3); }
.step-icon-sm { font-size: 13px; flex-shrink: 0; }
.step-label { flex: 1; word-break: break-word; }
.step-indent { padding-left: calc(14px + var(--indent, 0) * 14px); }

/* ===== MAIN WORKFLOW CANVAS ===== */
#canvas {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
    background: #f5f7fa;
}
#canvas-inner {
    max-width: 860px;
    margin: 0 auto;
}
.wf-step-card {
    background: var(--sp-white);
    border: 1px solid #c8d8ea;
    border-radius: 4px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: box-shadow 0.15s, border-color 0.15s;
    position: relative;
    overflow: hidden;
}
.wf-step-card:hover { box-shadow: 0 2px 8px rgba(0,114,198,0.18); border-color: var(--sp-blue); }
.wf-step-card.selected { box-shadow: 0 0 0 2px var(--sp-blue); border-color: var(--sp-blue); }
.wf-step-header {
    display: flex;
    align-items: center;
    padding: 9px 12px;
    gap: 10px;
    border-left: 5px solid #ccc;
}
.wf-step-body {
    padding: 0 12px 10px 40px;
    font-size: 12px;
    color: var(--sp-gray);
    display: none;
    border-top: 1px solid #f0f0f0;
    padding-top: 8px;
}
.wf-step-body.open { display: block; }
.wf-step-number {
    min-width: 26px;
    height: 26px;
    border-radius: 13px;
    background: var(--sp-blue-dark);
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.wf-step-icon { font-size: 18px; flex-shrink: 0; }
.wf-step-name { font-size: 13px; font-weight: 600; color: #1a3a5c; flex: 1; }
.wf-step-type { font-size: 10px; color: var(--sp-gray); }
.wf-step-expand { font-size: 11px; color: var(--sp-gray); cursor: pointer; padding: 2px 6px; border-radius: 3px; }
.wf-step-expand:hover { background: var(--sp-gray-light); }

/* Activity color coding — left border */
.act-log       .wf-step-header { border-left-color: #9E9E9E; }
.act-email     .wf-step-header { border-left-color: #0072C6; }
.act-task      .wf-step-header { border-left-color: #E87722; }
.act-field     .wf-step-header { border-left-color: #4CAF50; }
.act-condition .wf-step-header { border-left-color: #FFC107; }
.act-branch    .wf-step-header { border-left-color: #FFD54F; background: #fffde7; }
.act-parallel  .wf-step-header { border-left-color: #7B1FA2; background: #f3e5f5; }
.act-sequence  .wf-step-header { border-left-color: #00796B; }
.act-wait      .wf-step-header { border-left-color: #5C6BC0; }
.act-calc      .wf-step-header { border-left-color: #00897B; }
.act-default   .wf-step-header { border-left-color: #78909C; }

/* Nested indentation */
.nest-1 { margin-left: 20px; }
.nest-2 { margin-left: 40px; }
.nest-3 { margin-left: 60px; }
.nest-4 { margin-left: 80px; }

/* Connector line */
.connector {
    width: 2px;
    height: 10px;
    background: var(--sp-blue-light);
    margin-left: calc(20px + var(--nest,0) * 20px + 13px);
    margin-bottom: 0;
}
.connector.branch-start::before {
    content: "";
    display: block;
    width: 60px;
    height: 2px;
    background: var(--sp-blue-light);
    margin-top: 4px;
}

/* Container header */
.container-card {
    border: 2px dashed #b8d0e8;
    border-radius: 5px;
    margin-bottom: 8px;
    background: rgba(240,248,255,0.6);
}
.container-card .wf-step-header { background: rgba(0,114,198,0.06); }
.container-card.act-condition { border-color: #ffe082; background: rgba(255,253,231,0.7); }
.container-card.act-parallel  { border-color: #ce93d8; background: rgba(243,229,245,0.6); }
.container-card.act-branch    { border-color: #ffd54f; }

/* ===== RIGHT PROPERTIES PANEL ===== */
#props-panel {
    width: var(--props-w);
    background: #fff;
    border-left: 1px solid var(--sp-gray-mid);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    overflow: hidden;
}
#props-tabs {
    display: flex;
    background: #f5f7fa;
    border-bottom: 2px solid var(--sp-blue);
    flex-shrink: 0;
}
.props-tab {
    padding: 7px 12px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    color: var(--sp-gray);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    white-space: nowrap;
    transition: color 0.12s, border-color 0.12s;
}
.props-tab:hover { color: var(--sp-blue); }
.props-tab.active { color: var(--sp-blue-dark); border-bottom-color: var(--sp-blue-dark); background: #fff; }
#props-body {
    overflow-y: auto;
    flex: 1;
    padding: 10px 12px;
}
.tab-pane { display: none; }
.tab-pane.active { display: block; }

/* Property table */
.prop-section { margin-bottom: 14px; }
.prop-section-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--sp-blue-dark);
    border-bottom: 1px solid var(--sp-blue-light);
    padding-bottom: 4px;
    margin-bottom: 7px;
}
.prop-row {
    display: flex;
    padding: 3px 0;
    border-bottom: 1px solid #f5f5f5;
    gap: 6px;
    align-items: flex-start;
}
.prop-key {
    min-width: 100px;
    font-size: 11px;
    color: var(--sp-gray);
    font-weight: 600;
    flex-shrink: 0;
}
.prop-val {
    font-size: 11px;
    color: var(--sp-gray-dark);
    word-break: break-word;
    flex: 1;
}
.prop-badge {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    background: var(--sp-blue-light);
    color: var(--sp-blue-dark);
}
.prop-badge.green  { background: #e8f5e9; color: #2e7d32; }
.prop-badge.orange { background: #fff3e0; color: #e65100; }
.prop-badge.yellow { background: #fffde7; color: #f57f17; }
.prop-badge.gray   { background: #f5f5f5; color: #616161; }

/* Variables table */
.var-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.var-table th { background: var(--sp-blue-dark); color: #fff; padding: 4px 6px; text-align: left; font-size: 10px; }
.var-table td { padding: 4px 6px; border-bottom: 1px solid #f0f0f0; }
.var-table tr:hover td { background: var(--sp-blue-light); }

/* Field updates list */
.field-update-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 11px;
}
.field-update-item .fu-field { font-weight: 600; color: #2e7d32; }
.field-update-item .fu-arrow { color: var(--sp-gray); }
.field-update-item .fu-val { color: var(--sp-gray-dark); }

/* ===== TOOLTIP ===== */
[data-tooltip] { position: relative; }
[data-tooltip]:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: #1a3a5c;
    color: #fff;
    font-size: 10px;
    padding: 4px 8px;
    border-radius: 3px;
    white-space: pre-wrap;
    max-width: 250px;
    z-index: 1000;
    pointer-events: none;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    line-height: 1.4;
}

/* ===== STATUS BAR ===== */
#statusbar {
    background: var(--sp-blue-dark);
    color: rgba(255,255,255,0.7);
    font-size: 10px;
    padding: 2px 14px;
    display: flex;
    gap: 20px;
    align-items: center;
    flex-shrink: 0;
    height: 20px;
}
#statusbar span { white-space: nowrap; }

/* ===== SCROLLBAR STYLES ===== */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #b0c4d8; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #7a9fbf; }

/* ===== PRINT STYLES ===== */
@media print {
    #ribbon, #breadcrumb, #sidebar, #props-panel, #statusbar { display: none !important; }
    #workspace { height: auto; overflow: visible; display: block; }
    #canvas { overflow: visible; height: auto; }
    .wf-step-body { display: block !important; }
    body { overflow: visible; height: auto; font-size: 11px; }
    .wf-step-card { break-inside: avoid; }
}

/* ===== SEARCH HIGHLIGHT ===== */
.hl { background: #fff176; border-radius: 2px; }

/* ===== EMPTY STATE ===== */
.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--sp-gray);
}
.empty-state .es-icon { font-size: 48px; margin-bottom: 10px; }

/* ===== LEGEND ===== */
.legend { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    color: var(--sp-gray-dark);
}
.legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
}
"""

JS = r"""
// =========================================================
// State
// =========================================================
let selectedStepId = null;
const stepsData = __STEPS_DATA__;
const workflowMeta = __META_DATA__;

// =========================================================
// Sidebar search
// =========================================================
document.getElementById('sidebar-search-input').addEventListener('input', function() {
    const q = this.value.trim().toLowerCase();
    document.querySelectorAll('.step-item').forEach(function(el) {
        const label = el.querySelector('.step-label').textContent.toLowerCase();
        el.style.display = (q === '' || label.includes(q)) ? '' : 'none';
    });
});

// =========================================================
// Step selection
// =========================================================
function selectStep(stepId) {
    // Deselect all
    document.querySelectorAll('.wf-step-card').forEach(function(c) { c.classList.remove('selected'); });
    document.querySelectorAll('.step-item').forEach(function(s) { s.classList.remove('active'); });

    if (!stepId) return;
    selectedStepId = stepId;

    // Highlight card
    const card = document.getElementById('card_' + stepId);
    if (card) {
        card.classList.add('selected');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Highlight sidebar item
    const sItem = document.getElementById('sitem_' + stepId);
    if (sItem) {
        sItem.classList.add('active');
        sItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Populate properties panel
    populateProps(stepId);
}

// =========================================================
// Toggle step body
// =========================================================
function toggleBody(stepId, event) {
    event.stopPropagation();
    const body = document.getElementById('body_' + stepId);
    if (!body) return;
    const btn = document.getElementById('expand_' + stepId);
    if (body.classList.contains('open')) {
        body.classList.remove('open');
        if (btn) btn.textContent = '+';
    } else {
        body.classList.add('open');
        if (btn) btn.textContent = '−';
    }
}

// =========================================================
// Expand / Collapse all
// =========================================================
function expandAll() {
    document.querySelectorAll('.wf-step-body').forEach(function(b) { b.classList.add('open'); });
    document.querySelectorAll('.wf-step-expand').forEach(function(b) { b.textContent = '−'; });
}
function collapseAll() {
    document.querySelectorAll('.wf-step-body').forEach(function(b) { b.classList.remove('open'); });
    document.querySelectorAll('.wf-step-expand').forEach(function(b) { b.textContent = '+'; });
}

// =========================================================
// Properties panel
// =========================================================
function populateProps(stepId) {
    const step = stepsData[stepId];
    if (!step) return;

    // Switch to Activity tab
    switchTab('tab-activity');

    const pane = document.getElementById('tab-activity');
    let rows = '';

    // Basic info section
    rows += '<div class="prop-section">';
    rows += '<div class="prop-section-title">Activity Information</div>';
    rows += propRow('Name', escHtml(step.display_name));
    rows += propRow('Step #', step.step_number);
    rows += propRow('Type', '<span class="prop-badge">' + escHtml(step.meta.label) + '</span>');
    rows += propRow('Category', escHtml(step.meta.category));
    rows += '</div>';

    // Attributes section
    const importantKeys = ['to','subject','body','fieldname','fieldvalue','historyoutcome',
        'historydescription','tasktitle','assignedto','description','duedate',
        'priority','result','comment','listid','listitem',
        'taskoutcome','datefieldfrom','offset','offsetunit'];
    const attrKeys = Object.keys(step.attrs).filter(function(k) {
        return !['x:name','name','displayname','__context'].includes(k.toLowerCase());
    });

    if (attrKeys.length > 0) {
        rows += '<div class="prop-section">';
        rows += '<div class="prop-section-title">Properties</div>';
        // Important keys first
        importantKeys.forEach(function(k) {
            if (step.attrs[k] !== undefined) {
                rows += propRow(titleCase(k), escHtml(cleanVal(step.attrs[k])));
            }
        });
        // Remaining
        attrKeys.forEach(function(k) {
            if (!importantKeys.includes(k.toLowerCase())) {
                rows += propRow(titleCase(k), escHtml(cleanVal(step.attrs[k])));
            }
        });
        rows += '</div>';
    }

    // Field updates
    if (step.field_updates && step.field_updates.length > 0) {
        rows += '<div class="prop-section">';
        rows += '<div class="prop-section-title">Field Updates</div>';
        step.field_updates.forEach(function(fu) {
            rows += '<div class="field-update-item">' +
                '<span class="fu-field">' + escHtml(fu.field) + '</span>' +
                '<span class="fu-arrow">&#8594;</span>' +
                '<span class="fu-val">' + escHtml(fu.value) + '</span>' +
                '</div>';
        });
        rows += '</div>';
    }

    pane.innerHTML = rows;
}

function propRow(key, val) {
    return '<div class="prop-row"><span class="prop-key">' + key + '</span><span class="prop-val">' + val + '</span></div>';
}

function escHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function cleanVal(val) {
    if (!val) return '';
    var m = val.match(/Path=([^,}]+)/);
    if (m) return '[Variable: ' + m[1].trim() + ']';
    return val.replace(/\{workflow:(\w+)\}/g, '[$1]');
}

function titleCase(str) {
    return str.replace(/([A-Z])/g, ' $1').replace(/^./, function(s) { return s.toUpperCase(); }).trim();
}

// =========================================================
// Tab switching
// =========================================================
function switchTab(tabId) {
    document.querySelectorAll('.props-tab').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.tab-pane').forEach(function(p) { p.classList.remove('active'); });
    const tab = document.querySelector('[data-tab="' + tabId + '"]');
    const pane = document.getElementById(tabId);
    if (tab) tab.classList.add('active');
    if (pane) pane.classList.add('active');
}

// =========================================================
// Print
// =========================================================
function printWorkflow() {
    expandAll();
    setTimeout(function() { window.print(); }, 300);
}

// =========================================================
// Init
// =========================================================
window.addEventListener('DOMContentLoaded', function() {
    // Populate workflow-level properties tab
    const wfPane = document.getElementById('tab-workflow');
    let wfRows = '';
    wfRows += '<div class="prop-section"><div class="prop-section-title">Workflow Settings</div>';
    wfRows += propRow('Name', escHtml(workflowMeta.name));
    wfRows += propRow('Description', escHtml(workflowMeta.description));
    wfRows += propRow('Author', escHtml(workflowMeta.author));
    wfRows += propRow('Created', escHtml(workflowMeta.created));
    wfRows += propRow('Modified', escHtml(workflowMeta.modified));
    wfRows += propRow('Associated List', escHtml(workflowMeta.list_url));

    var startTriggers = [];
    if (workflowMeta.start_manually === 'true') startTriggers.push('Manually');
    if (workflowMeta.start_on_create === 'true') startTriggers.push('Item Created');
    if (workflowMeta.start_on_change === 'true') startTriggers.push('Item Changed');
    wfRows += propRow('Start Options', escHtml(startTriggers.join(', ') || 'Manually'));
    wfRows += '</div>';

    if (workflowMeta.variables && workflowMeta.variables.length > 0) {
        wfRows += '<div class="prop-section"><div class="prop-section-title">Workflow Variables</div>';
        wfRows += '<table class="var-table"><thead><tr><th>Name</th><th>Type</th><th>Default</th></tr></thead><tbody>';
        workflowMeta.variables.forEach(function(v) {
            wfRows += '<tr><td>' + escHtml(v.name) + '</td><td>' + escHtml(v.type) + '</td><td>' + escHtml(v.default) + '</td></tr>';
        });
        wfRows += '</tbody></table></div>';
    }
    wfPane.innerHTML = wfRows;

    // Select first step if available
    var firstCard = document.querySelector('.wf-step-card');
    if (firstCard) {
        var fid = firstCard.id.replace('card_', '');
        selectStep(fid);
    }
});
"""


def build_step_detail_html(node: dict) -> str:
    """Build the collapsible body HTML for a step card."""
    tag = node["tag"]
    attrs = node["attrs"]
    parts = []

    def attr_row(label: str, key: str) -> str:
        val = attrs.get(key, "")
        if not val:
            return ""
        return (
            f'<div class="prop-row">'
            f'<span class="prop-key">{html.escape(label)}</span>'
            f'<span class="prop-val">{html.escape(clean_value(val))}</span>'
            f"</div>"
        )

    # Per-type detail rows
    if tag in ("sendemailactivity", "sendemail"):
        for k, lbl in [("To", "to"), ("Subject", "subject"), ("CC", "cc")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)
        body_val = attrs.get("body") or attrs.get("Body", "")
        if body_val:
            safe_body = html.escape(body_val).replace("&#xA;", "<br>")
            parts.append(
                f'<div class="prop-row">'
                f'<span class="prop-key">Body</span>'
                f'<span class="prop-val" style="white-space:pre-wrap;font-size:11px">{safe_body}</span>'
                f"</div>"
            )

    elif tag in ("setfieldactivity",):
        for k, lbl in [("Field", "fieldname"), ("Value", "fieldvalue")]:
            parts.append(attr_row(k, lbl))

    elif tag == "setfield":
        for k, lbl in [("Field", "field"), ("Value", "value")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)

    elif tag in ("createtaskwithcontenttypeactivity", "createtaskactivity", "createtask"):
        for k, lbl in [("Title", "tasktitle"), ("Assigned To", "assignedto"),
                       ("Due Date", "duedate"), ("Priority", "priority"),
                       ("Description", "description")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)

    elif tag in ("completetask",):
        for k, lbl in [("Task ID", "taskid"), ("Outcome", "outcome")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)

    elif tag == "setworkflowvariable":
        for k, lbl in [("Variable", "variablename"), ("Value", "value")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)

    elif tag == "delayfor":
        r = attr_row("Duration", "duration")
        if r:
            parts.append(r)

    elif tag in ("logtohistorylistactivity", "logtohistorylist"):
        for k, lbl in [("Outcome", "historyoutcome"), ("Description", "historydescription"), ("Comment", "comment")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)

    elif tag == "builddateactivity":
        for k, lbl in [("From", "datefieldfrom"), ("Offset", "offset"), ("Unit", "offsetunit"), ("Result", "result")]:
            r = attr_row(k, lbl)
            if r:
                parts.append(r)

    elif tag == "updatelistitemactivity":
        for fu in node.get("field_updates", []):
            parts.append(
                f'<div class="field-update-item">'
                f'<span class="fu-field">{html.escape(fu["field"])}</span>'
                f'<span class="fu-arrow">&#8594;</span>'
                f'<span class="fu-val">{html.escape(fu["value"])}</span>'
                f"</div>"
            )

    return "".join(parts)


def render_card(node: dict, step_counter_ref: list) -> str:
    """Render a single activity node as an HTML step card string."""
    tag = node["tag"]
    meta = node["meta"]
    display_name = node["display_name"]
    depth = node.get("depth", 0)
    step_id = node.get("step_id", f"step_{id(node)}")
    step_num = node.get("step_number", "")

    indent_class = f"nest-{min(depth, 4)}" if depth > 0 else ""
    color_class = meta["color"]
    icon = meta["icon"]
    container = is_container(tag)
    card_class = "container-card" if container else "wf-step-card"

    body_html = build_step_detail_html(node)
    has_body = bool(body_html) or len(node.get("children", [])) > 0

    # Tooltip with key info
    tooltip_parts = [display_name, f"Type: {meta['label']}", f"Category: {meta['category']}"]
    if "historyoutcome" in node["attrs"]:
        tooltip_parts.append(f"Outcome: {node['attrs']['historyoutcome']}")
    if "to" in node["attrs"]:
        tooltip_parts.append(f"To: {clean_value(node['attrs']['to'])}")
    tooltip = "&#10;".join(tooltip_parts)

    step_num_html = f'<div class="wf-step-number">{step_num}</div>' if step_num else ""
    expand_btn = (
        f'<span class="wf-step-expand" id="expand_{step_id}" '
        f'onclick="toggleBody(\'{step_id}\', event)">+</span>'
        if has_body
        else ""
    )

    html_parts = [
        f'<div id="card_{step_id}" class="{card_class} {color_class} {indent_class}" '
        f'onclick="selectStep(\'{step_id}\')" data-tooltip="{html.escape(tooltip)}">',
        f'  <div class="wf-step-header">',
        f"    {step_num_html}",
        f'    <span class="wf-step-icon">{icon}</span>',
        f'    <div style="flex:1">',
        f'      <div class="wf-step-name">{html.escape(display_name)}</div>',
        f'      <div class="wf-step-type">{html.escape(meta["label"])} &bull; {html.escape(meta["category"])}</div>',
        f"    </div>",
        f"    {expand_btn}",
        f"  </div>",
    ]

    if has_body:
        html_parts.append(
            f'  <div class="wf-step-body" id="body_{step_id}">{body_html}</div>'
        )

    html_parts.append("</div>")

    # Recurse into children
    for child in node.get("children", []):
        html_parts.append(render_card(child, step_counter_ref))

    return "\n".join(html_parts)


def build_sidebar_items(steps: list) -> str:
    """Build the left sidebar step list HTML."""
    items = []
    for step in steps:
        meta = step["meta"]
        sid = step.get("step_id", "")
        snum = step.get("step_number", "")
        depth = step.get("depth", 0)
        indent = min(depth, 4)
        label = html.escape(step["display_name"])
        items.append(
            f'<div class="step-item step-indent" id="sitem_{sid}" '
            f'style="--indent:{indent}" onclick="selectStep(\'{sid}\')">'
            f'<span class="step-num">{snum}</span>'
            f'<span class="step-icon-sm">{meta["icon"]}</span>'
            f'<span class="step-label">{label}</span>'
            f"</div>"
        )
    return "\n".join(items)


def build_legend_html() -> str:
    legend_items = [
        ("#9E9E9E", "Log/History"),
        ("#0072C6", "Email"),
        ("#E87722", "Task"),
        ("#4CAF50", "Set Field"),
        ("#FFC107", "Condition"),
        ("#7B1FA2", "Parallel"),
        ("#5C6BC0", "Wait"),
        ("#00897B", "Calculate"),
        ("#78909C", "Other"),
    ]
    parts = ['<div class="legend">']
    for color, label in legend_items:
        parts.append(
            f'<div class="legend-item">'
            f'<div class="legend-dot" style="background:{color}"></div>'
            f'{html.escape(label)}'
            f"</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def generate_html(root_node: dict, wf_meta: dict, steps: list, source_file: str) -> str:
    """Generate the complete HTML document."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wf_name = html.escape(wf_meta["name"])
    wf_desc = html.escape(wf_meta.get("description", ""))
    source_base = html.escape(os.path.basename(source_file))
    total_steps = sum(1 for s in steps if s.get("step_number"))

    # Build steps data dict for JS
    steps_dict = {}
    for s in steps:
        sid = s.get("step_id")
        if sid:
            steps_dict[sid] = {
                "display_name": s["display_name"],
                "step_number": s.get("step_number", ""),
                "meta": s["meta"],
                "attrs": {k: v for k, v in s["attrs"].items()
                          if k.lower() not in ("__context",)},
                "field_updates": s.get("field_updates", []),
            }

    steps_json = json.dumps(steps_dict, ensure_ascii=False)
    meta_json = json.dumps(wf_meta, ensure_ascii=False)

    # Render canvas cards
    canvas_cards = render_card(root_node, [0])

    sidebar_items = build_sidebar_items(steps)
    legend_html = build_legend_html()

    # Inline JS with data injected
    js_code = JS.replace("__STEPS_DATA__", steps_json).replace("__META_DATA__", meta_json)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{wf_name} - SharePoint Designer</title>
  <style>{CSS}</style>
</head>
<body>

<!-- ===== RIBBON ===== -->
<div id="ribbon">
  <div id="ribbon-top">
    <div id="ribbon-logo">
      <span class="sp-icon">&#128196;</span>
      SharePoint Designer 2013
    </div>
    <span id="ribbon-subtitle">Workflow Editor</span>
  </div>
  <div id="ribbon-bottom">
    <div id="wf-name-ribbon">&#9654; {wf_name}</div>
    <button class="ribbon-btn" onclick="expandAll()" data-tooltip="Expand all steps">
      &#9660; Expand All
    </button>
    <button class="ribbon-btn" onclick="collapseAll()" data-tooltip="Collapse all steps">
      &#9650; Collapse All
    </button>
    <button class="ribbon-btn" onclick="printWorkflow()" data-tooltip="Print workflow">
      &#128438; Print
    </button>
    <button class="ribbon-btn" onclick="switchTab('tab-workflow')" data-tooltip="Workflow properties">
      &#9881; Properties
    </button>
  </div>
</div>

<!-- ===== BREADCRUMB ===== -->
<div id="breadcrumb">
  <a href="#">Site</a>
  <span>&#8250;</span>
  <a href="#">Workflows</a>
  <span>&#8250;</span>
  <strong>{wf_name}</strong>
  <span style="margin-left:auto;color:#888">Source: {source_base}</span>
</div>

<!-- ===== WORKSPACE ===== -->
<div id="workspace">

  <!-- LEFT SIDEBAR -->
  <div id="sidebar">
    <div id="sidebar-header">&#9776; Workflow Steps ({total_steps})</div>
    <div id="sidebar-search">
      <input type="text" id="sidebar-search-input" placeholder="&#128269; Filter steps..." />
    </div>
    <div id="step-list">
      {sidebar_items}
    </div>
  </div>

  <!-- MAIN CANVAS -->
  <div id="canvas">
    <div id="canvas-inner">
      <!-- Legend -->
      <div style="margin-bottom:12px;padding:8px 12px;background:#fff;border:1px solid #d0e0f0;border-radius:4px;">
        <div style="font-size:10px;font-weight:700;color:#003366;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">Activity Legend</div>
        {legend_html}
      </div>

      <!-- Step cards -->
      {canvas_cards}

      <!-- Footer -->
      <div style="margin-top:20px;padding:10px;text-align:center;color:#aaa;font-size:10px;border-top:1px solid #e0e0e0;">
        Generated from <strong>{source_base}</strong> &bull; {now} &bull; {total_steps} steps
      </div>
    </div>
  </div>

  <!-- RIGHT PROPERTIES PANEL -->
  <div id="props-panel">
    <div id="props-tabs">
      <div class="props-tab active" data-tab="tab-activity" onclick="switchTab('tab-activity')">Activity</div>
      <div class="props-tab" data-tab="tab-workflow" onclick="switchTab('tab-workflow')">Workflow</div>
      <div class="props-tab" data-tab="tab-help" onclick="switchTab('tab-help')">Help</div>
    </div>
    <div id="props-body">
      <div class="tab-pane active" id="tab-activity">
        <div class="empty-state">
          <div class="es-icon">&#9654;</div>
          <div>Click an activity to view its properties</div>
        </div>
      </div>
      <div class="tab-pane" id="tab-workflow">
        <!-- Populated by JS -->
      </div>
      <div class="tab-pane" id="tab-help">
        <div class="prop-section">
          <div class="prop-section-title">About This Tool</div>
          <p style="font-size:11px;line-height:1.6;color:#555;margin-bottom:8px;">
            This HTML file was generated by <strong>sp_workflow_converter.py</strong>
            from a SharePoint 2013 Designer workflow XML/XOML file.
          </p>
          <div class="prop-section-title">How To Use</div>
          <p style="font-size:11px;line-height:1.6;color:#555;">
            &#8226; Click any step in the canvas or sidebar to view its properties.<br>
            &#8226; Use <strong>+/−</strong> buttons to expand/collapse step details.<br>
            &#8226; Use the ribbon buttons to expand/collapse all steps.<br>
            &#8226; Use the Workflow tab to see global workflow settings and variables.<br>
            &#8226; Click Print to get a printer-friendly version.
          </p>
        </div>
        <div class="prop-section">
          <div class="prop-section-title">Color Legend</div>
          {legend_html}
        </div>
      </div>
    </div>
  </div>

</div><!-- /workspace -->

<!-- ===== STATUS BAR ===== -->
<div id="statusbar">
  <span>&#128196; {wf_name}</span>
  <span>&#9654; {total_steps} Steps</span>
  <span>&#128197; Generated: {now}</span>
  <span style="margin-left:auto">SharePoint Designer 2013 Workflow Viewer</span>
</div>

<script>
{js_code}
</script>
</body>
</html>
"""
    return doc


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python sp_workflow_converter.py <workflow.xml>")
        print("Example: python sp_workflow_converter.py sample_workflow.xml")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Determine output path
    base, _ = os.path.splitext(input_path)
    output_path = base + ".html"

    print(f"[*] Parsing: {input_path}")

    # Collect namespaces for diagnostics
    ns_map = collect_namespaces(input_path)
    print(f"[*] Found {len(ns_map)} namespace(s):")
    for prefix, uri in ns_map.items():
        print(f"    {prefix!r}: {uri}")

    # Parse the XML tree
    try:
        tree = ET.parse(input_path)
    except ET.ParseError as exc:
        print(f"Error: XML parse error: {exc}")
        sys.exit(1)

    root = tree.getroot()
    print(f"[*] Root element: {root.tag}")

    # Extract workflow metadata
    wf_meta = extract_workflow_meta(root)
    print(f"[*] Workflow name: {wf_meta['name']}")
    print(f"[*] Variables: {len(wf_meta['variables'])}")

    # Parse activity tree
    STEP_COUNTER[0] = 0
    root_node = parse_element(root, depth=0)

    # Flatten steps for sidebar / JS data
    steps = []
    flatten_steps(root_node, steps)
    print(f"[*] Total activity steps: {len(steps)}")

    # Generate HTML
    doc = generate_html(root_node, wf_meta, steps, input_path)

    # Write output
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(doc)

    print(f"[+] Output written to: {output_path}")
    print(f"[+] File size: {os.path.getsize(output_path):,} bytes")
    print("[+] Done! Open the HTML file in a browser to view the workflow.")


if __name__ == "__main__":
    main()
