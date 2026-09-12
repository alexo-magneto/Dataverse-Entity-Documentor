import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dataverse_app_documentor.parsers import parse_fetch_entities, parse_form_xml, parse_sitemap_xml  # noqa: E402

SITEMAP = """
<SiteMap IntroducedVersion="7.0.0.0">
  <Area Id="SFA" ResourceId="Area_Sales" ShowGroups="true" Icon="/_imgs/sales_24x24.gif">
    <Titles><Title LCID="1033" Title="Sales"/></Titles>
    <Group Id="MyWork">
      <Titles><Title LCID="1033" Title="My Work"/></Titles>
      <SubArea Id="nav_dashboards" Url="/workplace/home_dashboards.aspx" DefaultDashboard="{2E3D0841-FA6D-4A6A-8B76-6A0B1B2C3D4E}">
        <Titles><Title LCID="1033" Title="Dashboards"/></Titles>
      </SubArea>
      <SubArea Id="nav_accts" Entity="account"/>
      <SubArea Id="nav_conts" Entity="contact"/>
      <SubArea Id="nav_wr" Url="$webresource:new_/pages/help.html" Title="Help"/>
    </Group>
  </Area>
</SiteMap>
"""

FORM = """
<form>
  <tabs>
    <tab name="general" id="{1}"><labels><label description="General" languagecode="1033"/></labels>
      <columns><column width="50%"><sections>
        <section name="s1" id="{2}"><labels><label description="Account Info" languagecode="1033"/></labels>
          <rows>
            <row><cell id="{c1}"><control id="name" classid="{4273EDBD-AC1D-40d3-9FB2-095C621B552D}" datafieldname="name"/></cell></row>
            <row><cell id="{c2}"><control id="primarycontactid" classid="{270BD3DB-D9AF-4782-9025-509E298DEC0A}" datafieldname="primarycontactid"/></cell></row>
            <row><cell id="{c3}"><control id="Contacts" classid="{E7A81278-8635-4d9e-8D4D-59480B391C5B}">
              <parameters><ViewId>{00000000-0000-0000-00AA-000010001004}</ViewId><TargetEntityType>contact</TargetEntityType><RelationshipName>contact_customer_accounts</RelationshipName></parameters>
            </control></cell></row>
            <row><cell id="{c4}"><control id="qv" classid="{5C5600E0-1D6E-4205-A272-BE80DA87FD42}" datafieldname="primarycontactid">
              <parameters><QuickForms><QuickFormIds><QuickFormId entityname="contact">{A1B2C3D4-0000-0000-0000-000000000001}</QuickFormId></QuickFormIds></QuickForms></parameters>
            </control></cell></row>
            <row><cell id="{c5}"><control id="Timeline" classid="{06375649-C143-495e-A496-C962E5B4488E}" uniqueid="{99999999-0000-0000-0000-000000000009}">
              <parameters><TimelineWallControl><EnabledModules>email,phonecall,task,new_customactivity</EnabledModules></TimelineWallControl></parameters>
            </control></cell></row>
          </rows>
        </section>
      </sections></column></columns>
    </tab>
  </tabs>
  <header><rows><row><cell id="{h1}"><control id="header_ownerid" classid="{270BD3DB-D9AF-4782-9025-509E298DEC0A}" datafieldname="ownerid"/></cell></row></rows></header>
  <controlDescriptions>
    <controlDescription forControl="{99999999-0000-0000-0000-000000000009}">
      <customControl formFactor="2" name="MscrmControls.Timeline.TimelineControl"/>
    </controlDescription>
  </controlDescriptions>
  <Navigation><NavBar><NavBarByRelationshipItem Id="navOpps" RelationshipName="opportunity_customer_accounts"/></NavBar></Navigation>
</form>
"""

DASHBOARD = """
<form><tabs><tab id="{t}" name="dash"><labels><label description="Sales Dashboard" languagecode="1033"/></labels><columns><column><sections><section id="{s}" name="s">
<rows><row><cell id="{a}"><control id="Chart1" classid="{E7A81278-8635-4d9e-8D4D-59480B391C5B}"><parameters><TargetEntityType>opportunity</TargetEntityType><ViewId>{V1}</ViewId><VisualizationId>{C1}</VisualizationId></parameters></control></cell></row>
<row><cell id="{b}"><control id="List1" classid="{E7A81278-8635-4d9e-8D4D-59480B391C5B}"><parameters><TargetEntityType>lead</TargetEntityType><ViewId>{V2}</ViewId></parameters></control></cell></row>
</rows></section></sections></column></columns></tab></tabs></form>
"""

CHART_DATA = """
<datadefinition><fetchcollection><fetch mapping="logical" aggregate="true"><entity name="opportunity"><attribute name="estimatedvalue" aggregate="sum" alias="v"/>
<link-entity name="systemuser" from="systemuserid" to="ownerid"><attribute name="fullname" groupby="true" alias="o"/></link-entity></entity></fetch></fetchcollection></datadefinition>
"""


class SiteMapTests(unittest.TestCase):
    def test_nodes(self):
        nodes = parse_sitemap_xml(SITEMAP)
        kinds = [n.kind for n in nodes]
        self.assertEqual(kinds.count("Area"), 1)
        self.assertEqual(kinds.count("Group"), 1)
        self.assertEqual(kinds.count("SubArea"), 4)
        self.assertEqual({n.entity for n in nodes if n.entity}, {"account", "contact"})
        dash = [n for n in nodes if n.dashboard_id][0]
        self.assertEqual(dash.dashboard_id, "2e3d0841-fa6d-4a6a-8b76-6a0b1b2c3d4e")
        self.assertEqual(dash.title, "Dashboards")
        self.assertEqual([n.web_resource for n in nodes if n.web_resource], ["new_/pages/help.html"])
        self.assertEqual(nodes[0].title, "Sales")


class FormTests(unittest.TestCase):
    def test_controls(self):
        f = parse_form_xml(FORM)
        self.assertEqual(f.parse_error, "")
        self.assertEqual([t.label for t in f.tabs], ["General"])
        self.assertEqual(f.tabs[0].sections, ["Account Info"])
        by_id = {c.control_id: c for c in f.controls}
        self.assertEqual(by_id["name"].kind, "Field")
        self.assertEqual(by_id["primarycontactid"].kind, "Lookup")
        self.assertEqual(by_id["Contacts"].kind, "Sub Grid")
        self.assertEqual(by_id["Contacts"].target_entity, "contact")
        self.assertEqual(by_id["Contacts"].view_id, "00000000-0000-0000-00aa-000010001004")
        self.assertEqual(by_id["Contacts"].relationship_name, "contact_customer_accounts")
        self.assertEqual(by_id["qv"].kind, "Quick View Form")
        self.assertEqual(by_id["qv"].quick_forms, [("contact", "a1b2c3d4-0000-0000-0000-000000000001")])
        self.assertEqual(by_id["Timeline"].kind, "Timeline")
        self.assertIn("MscrmControls.Timeline.TimelineControl", by_id["Timeline"].custom_control_names)
        self.assertEqual(by_id["header_ownerid"].tab, "(header/footer)")
        self.assertEqual(f.navigation_relationships, ["opportunity_customer_accounts"])

    def test_dashboard_chart_vs_list(self):
        f = parse_form_xml(DASHBOARD)
        by_id = {c.control_id: c for c in f.controls}
        self.assertEqual(by_id["Chart1"].kind, "Sub Grid")  # has ViewId -> subgrid-style list with chart
        self.assertEqual(by_id["Chart1"].visualization_id, "c1")
        self.assertEqual(by_id["List1"].kind, "Sub Grid")
        self.assertEqual(by_id["List1"].target_entity, "lead")

    def test_bad_xml(self):
        f = parse_form_xml("<form><tabs>")
        self.assertTrue(f.parse_error)


class FetchTests(unittest.TestCase):
    def test_view(self):
        primary, linked = parse_fetch_entities('<fetch><entity name="account"><link-entity name="contact" from="contactid" to="primarycontactid"><link-entity name="systemuser" from="systemuserid" to="ownerid"/></link-entity></entity></fetch>')
        self.assertEqual(primary, "account")
        self.assertEqual(linked, ["contact", "systemuser"])

    def test_chart_datadescription(self):
        primary, linked = parse_fetch_entities(CHART_DATA)
        self.assertEqual(primary, "opportunity")
        self.assertEqual(linked, ["systemuser"])


if __name__ == "__main__":
    unittest.main()
