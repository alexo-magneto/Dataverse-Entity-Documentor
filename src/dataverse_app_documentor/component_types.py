"""Reference tables: solution component types, form types, view types, control class ids."""

from __future__ import annotations

# appmodulecomponent.componenttype / solutioncomponent.componenttype
COMPONENT_TYPES: dict[int, str] = {
    1: "Entity",
    2: "Attribute",
    3: "Relationship",
    4: "Attribute Picklist Value",
    5: "Attribute Lookup Value",
    6: "View Attribute",
    7: "Localized Label",
    8: "Relationship Extra Condition",
    9: "Option Set",
    10: "Entity Relationship",
    11: "Entity Relationship Role",
    12: "Entity Relationship Relationships",
    13: "Managed Property",
    14: "Entity Key",
    16: "Privilege",
    17: "Privilege Object Type Code",
    20: "Security Role",
    21: "Role Privilege",
    22: "Display String",
    23: "Display String Map",
    24: "Form",
    25: "Organization",
    26: "View (Saved Query)",
    29: "Process (Workflow)",
    31: "Report",
    32: "Report Entity",
    33: "Report Category",
    34: "Report Visibility",
    35: "Attachment",
    36: "Email Template",
    37: "Contract Template",
    38: "KB Article Template",
    39: "Mail Merge Template",
    44: "Duplicate Rule",
    45: "Duplicate Rule Condition",
    46: "Entity Map",
    47: "Attribute Map",
    48: "Ribbon Command",
    49: "Ribbon Context Group",
    50: "Ribbon Customization",
    52: "Ribbon Rule",
    53: "Ribbon Tab To Command Map",
    55: "Ribbon Diff",
    59: "Chart (Saved Query Visualization)",
    60: "Form (System Form)",
    61: "Web Resource",
    62: "Site Map",
    63: "Connection Role",
    64: "Complex Control",
    65: "Hierarchy Rule",
    66: "Custom Control",
    68: "Custom Control Default Config",
    70: "Field Security Profile",
    71: "Field Permission",
    90: "Plugin Type",
    91: "Plugin Assembly",
    92: "SDK Message Processing Step",
    93: "SDK Message Processing Step Image",
    95: "Service Endpoint",
    150: "Routing Rule",
    151: "Routing Rule Item",
    152: "SLA",
    153: "SLA Item",
    154: "Convert Rule",
    155: "Convert Rule Item",
    161: "Mobile Offline Profile",
    162: "Mobile Offline Profile Item",
    165: "Similarity Rule",
    166: "Data Source Mapping",
    201: "SDK Message",
    202: "SDK Message Filter",
    203: "SDK Message Pair",
    204: "SDK Message Request",
    205: "SDK Message Request Field",
    206: "SDK Message Response",
    207: "SDK Message Response Field",
    208: "Import Map",
    210: "Web Wizard",
    300: "Canvas App",
    371: "Connector",
    372: "Connector (Custom)",
    380: "Environment Variable Definition",
    381: "Environment Variable Value",
    400: "AI Project Type",
    401: "AI Project",
    402: "AI Configuration",
    430: "Entity Analytics Configuration",
    431: "Attribute Image Configuration",
    432: "Entity Image Configuration",
}

# appmodulecomponent.rootcomponentbehavior
ROOT_COMPONENT_BEHAVIOR: dict[int, str] = {
    0: "Include Subcomponents",
    1: "Do not include subcomponents",
    2: "Include As Shell Only",
}

# systemform.type
FORM_TYPES: dict[int, str] = {
    0: "Dashboard",
    1: "Appointment Book",
    2: "Main Form",
    3: "Mini Campaign BO",
    4: "Preview Form",
    5: "Mobile Express Form",
    6: "Quick View Form",
    7: "Quick Create Form",
    8: "Dialog",
    9: "Task Flow Form",
    10: "Interaction Centric Dashboard",
    11: "Card Form",
    12: "Main Form (Interactive Experience)",
    13: "Contextual Dashboard",
    100: "Other",
    101: "Main Form Backup",
    102: "Appointment Book Backup",
    103: "Power BI Dashboard",
}
DASHBOARD_FORM_TYPES = {0, 10, 13, 103}

# systemform.formactivationstate
FORM_STATES: dict[int, str] = {0: "Inactive", 1: "Active"}

# savedquery.querytype
VIEW_TYPES: dict[int, str] = {
    0: "Public View (Main Application View)",
    1: "Advanced Search",
    2: "Sub Grid (Associated View)",
    4: "Quick Find",
    8: "Reporting",
    16: "Offline Filters",
    64: "Lookup View",
    128: "SM Appointment Book View",
    256: "Outlook Filters",
    512: "Address Book Filters",
    1024: "Main Application View Without Subject",
    2048: "Saved Query Type Other",
    4096: "Interactive Workflow View",
    8192: "Offline Template",
    16384: "Custom Definitional View",
    65536: "Copilot view",
}

# workflow.category
WORKFLOW_CATEGORIES: dict[int, str] = {
    0: "Workflow",
    1: "Dialog",
    2: "Business Rule",
    3: "Action",
    4: "Business Process Flow",
    5: "Modern Flow",
    6: "Desktop Flow",
    7: "AI Flow",
}

# webresource.webresourcetype
WEB_RESOURCE_TYPES: dict[int, str] = {
    1: "Webpage (HTML)",
    2: "Style Sheet (CSS)",
    3: "Script (JScript)",
    4: "Data (XML)",
    5: "PNG format",
    6: "JPG format",
    7: "GIF format",
    8: "Silverlight (XAP)",
    9: "Style Sheet (XSL)",
    10: "ICO format",
    11: "Vector format (SVG)",
    12: "String (RESX)",
}

# Form control classids (upper-cased, braces included).
CLASSID_SUBGRID = "{E7A81278-8635-4D9E-8D4D-59480B391C5B}"
CLASSID_LOOKUP = "{270BD3DB-D9AF-4782-9025-509E298DEC0A}"
CLASSID_QUICK_VIEW = "{5C5600E0-1D6E-4205-A272-BE80DA87FD42}"
CLASSID_NOTES_SOCIAL_PANE = "{06375649-C143-495E-A496-C962E5B4488E}"
CLASSID_WEB_RESOURCE = "{9FDF5F91-88B1-47F4-AD53-C11EFC01A01D}"
CLASSID_IFRAME = "{FD2A7985-3187-444E-908D-6624B21F69C0}"
CLASSID_PARTY_LIST = "{CBFB742C-14E7-4A17-96BB-1A13F7F64AA2}"
CLASSID_REGARDING = "{F3015350-44A2-4AA0-97B5-00166532B5E9}"
CLASSID_CUSTOMER_LOOKUP = "{4AA28AB7-9C13-4F57-A73D-AD894D048B5F}"
CLASSID_OWNER_LOOKUP = "{DDB2C4C4-77C6-4D3B-8A02-D2E1F9F1C6B9}"
CLASSID_BING_MAP = "{62B0DF79-0464-470F-8AF7-4483CFEA0C7D}"
CLASSID_TIMER = "{AA987274-CE4E-4271-A803-66164311A958}"
CLASSID_SPACER = "{7C624A0B-F59E-493D-9583-638D34759266}"

CONTROL_CLASSIDS: dict[str, str] = {
    "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}": "Single Line of Text",
    "{E0DECE4B-6FC8-4A8F-A065-082708572369}": "Multiple Lines of Text",
    "{F9A8A302-114E-466A-B582-6771B2AE0D92}": "Rich Text / Email Body",
    "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}": "Option Set",
    "{5B773807-9FB2-42DB-97C3-7A91EFF8ADFF}": "Date and Time",
    "{C3EFE0C3-0EC6-42BE-8349-CBD9079DFD8E}": "Decimal Number",
    "{0D2C745A-E5A8-4C8F-BA63-C6D3BB604660}": "Floating Point Number",
    "{533B9E00-756B-4312-95A0-DC888637AC78}": "Whole Number",
    "{C6D124CA-7EDA-4A60-AEA9-7FB8D318B68F}": "Currency",
    "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}": "Two Options (Radio)",
    "{B0C6723A-8503-4FD7-BB28-C8A06AC933C2}": "Two Options (Checkbox)",
    "{ADA2203E-B4CD-49BE-9DDF-234642B43B52}": "Duration",
    "{5D68B988-0661-4DB2-BC3E-17598AD3BE6C}": "Time Zone",
    "{71716B6C-711E-476C-8AB8-5D11542BFB47}": "Language",
    "{8C10015A-B339-4982-9474-A95FE05631A5}": "Ticker Symbol",
    "{1E1FC551-F7A8-43AF-AC34-A8DC35C7B6D4}": "Email Address",
    "{5C5600E0-1D6E-4205-A272-BE80DA87FD42}": "Quick View Form",
    "{E7A81278-8635-4D9E-8D4D-59480B391C5B}": "Sub Grid",
    "{270BD3DB-D9AF-4782-9025-509E298DEC0A}": "Lookup",
    "{06375649-C143-495E-A496-C962E5B4488E}": "Timeline / Notes / Social Pane",
    "{9FDF5F91-88B1-47F4-AD53-C11EFC01A01D}": "Web Resource",
    "{FD2A7985-3187-444E-908D-6624B21F69C0}": "IFrame",
    "{CBFB742C-14E7-4A17-96BB-1A13F7F64AA2}": "Party List",
    "{F3015350-44A2-4AA0-97B5-00166532B5E9}": "Regarding Lookup",
    "{4AA28AB7-9C13-4F57-A73D-AD894D048B5F}": "Customer Lookup",
    "{62B0DF79-0464-470F-8AF7-4483CFEA0C7D}": "Bing Map",
    "{AA987274-CE4E-4271-A803-66164311A958}": "Timer",
    "{7C624A0B-F59E-493D-9583-638D34759266}": "Spacer",
    "{C6375043-2E2C-4C39-A3D4-9C3E9DAB7BC7}": "Knowledge Base Search",
    "{DEC3D8B4-6A0D-4B2C-B6C0-7A5D0F4B5A2C}": "Business Process Flow",
    "{5546E6CD-394C-4BEE-94A8-4425E17EF6C6}": "Composite Address",
    "{F4A9ED4F-3E0C-4D0E-8F6E-8B0F5B0A3D2B}": "Image",
}

LOOKUP_CLASSIDS = {CLASSID_LOOKUP, CLASSID_PARTY_LIST, CLASSID_REGARDING, CLASSID_CUSTOMER_LOOKUP, CLASSID_OWNER_LOOKUP}
LOOKUP_ATTRIBUTE_TYPES = {"Lookup", "Customer", "Owner", "PartyList"}
