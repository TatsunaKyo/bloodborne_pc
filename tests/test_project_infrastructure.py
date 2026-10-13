# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check current documentation links, hardware evidence and CI/report contracts."""
import json
from pathlib import Path, PurePosixPath
import re
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]


class Infrastructure(unittest.TestCase):
    def test_readme_revision_matches_the_launcher(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from update_readme_revision import update
        self.assertFalse(update(check=True))

    def test_documentation_links_resolve(self):
        files=[ROOT/'README.md', ROOT/'CONTRIBUTING.md', ROOT/'SECURITY.md', *list((ROOT/'docs').rglob('*.md')),
               ROOT/'packaging/windows/README.md']
        # Historical upstream notes retain links to unavailable original-session
        # files. New canonical navigation and current guides must all resolve.
        current={'README.md','CONTRIBUTING.md','SECURITY.md','index.md','live-settings.md',
                 'known-issues.md','compatibility.md','repository-setup.md','infrastructure-plan.md',
                 'testing.md','releasing.md','launcher-and-menu.md','upscaling.md','frame-generation.md',
                 'latency.md','display-and-overlay.md','performance.md','quality-and-performance.md','cheats.md'}
        for file in files:
            text=file.read_text()
            is_current = file.parent == ROOT and file.name in current or file.parent == ROOT/'docs' and file.name in current or file.name == 'index.md'
            if not is_current:
                text='\n'.join(text.splitlines()[:3])
            for target in re.findall(r'\]\(([^)]+)\)',text):
                target=target.split('#',1)[0].split(' ',1)[0]
                if not target or '://' in target or target.startswith(('mailto:','app:')):continue
                with self.subTest(file=str(file.relative_to(ROOT)),target=target):
                    self.assertTrue((file.parent/target).exists())

    def test_editable_feature_images_resolve_local_resources(self):
        import xml.etree.ElementTree as ET
        directory=ROOT/'docs/assets/features'
        for source in directory.glob('*.svg'):
            for element in ET.parse(source).iter():
                if not element.tag.endswith('image'):
                    continue
                target=element.get('href',element.get('{http://www.w3.org/1999/xlink}href',''))
                if target.startswith('data:'):
                    continue
                with self.subTest(source=source.name,target=target):
                    self.assertTrue(target)
                    self.assertTrue((source.parent/target).is_file())

    def test_hardware_database_does_not_confuse_simulation_and_gameplay(self):
        data=json.loads((ROOT/'docs/hardware/compatibility.json').read_text())
        self.assertEqual(data['schema_version'],1)
        self.assertEqual(len({r['id'] for r in data['records']}),len(data['records']))
        for record in data['records']:
            self.assertIn(record['status'],('tested','partially-tested','unverified'))
            self.assertIs(record['reviewed'],True)
            if record['status']=='tested':
                self.assertIn('gameplay',record['evidence_kind'])
                self.assertIsInstance(record['port_revision'],int)
            if 'headless' in record['evidence_kind']:
                self.assertNotEqual(record['status'],'tested')

    def test_workflows_use_pinned_actions_and_read_only_permissions(self):
        workflows=list((ROOT/'.github/workflows').glob('*.yml'));self.assertEqual(len(workflows),3)
        for file in workflows:
            text=file.read_text()
            self.assertIn('contents: read',text)
            self.assertNotIn('pull_request_target:',text)
            self.assertNotIn('contents: write',text)
            for action in re.findall(r'uses:\s*([^\s#]+)',text):
                self.assertRegex(action,r'^[\w-]+/[\w-]+@[0-9a-f]{40}$')
        build=(ROOT/'.github/workflows/windows-build.yml').read_text()
        self.assertIn('Execute Windows regressions',build)
        self.assertIn('native-windows-tests.log',build)
        self.assertIn('tools/assemble_windows.py',build)
        self.assertNotIn('gh release create',build)
        self.assertIn('tools/verify_published_release.py',(ROOT/'.github/workflows/release-verification.yml').read_text())

    def test_yaml_and_workflow_triggers(self):
        for file in (ROOT/'.github').rglob('*.yml'):
            data=yaml.load(file.read_text(),Loader=yaml.BaseLoader)
            self.assertIsInstance(data,dict)
            if file.parent.name=='workflows':
                self.assertIn('on',data);self.assertIn('jobs',data)
            elif file.name!='config.yml':
                self.assertIn('body',data)

    def test_report_forms_collect_actionable_context(self):
        directory=ROOT/'.github/ISSUE_TEMPLATE'
        for name in ('bug-report.yml','performance-regression.yml','feature-request.yml'):
            text=(directory/name).read_text();ids=re.findall(r'^\s+id:\s*(\S+)',text,re.M)
            self.assertTrue(ids);self.assertEqual(len(ids),len(set(ids)))
            self.assertIn('body:',text)
            self.assertNotIn('token:',text)
        self.assertIn('both caps',(directory/'performance-regression.yml').read_text())

    def test_dependency_locks_are_verifiable(self):
        lock=json.loads((ROOT/'packaging/windows/msys2-packages.lock.json').read_text())
        self.assertGreater(len(lock),100)
        for name,record in lock.items():
            self.assertTrue(name.startswith('mingw-w64-clang-x86_64-'))
            self.assertEqual(PurePosixPath(record['filename']).name,record['filename'])
            self.assertRegex(record['sha256'],r'^[0-9a-f]{64}$')
        baseline=json.loads((ROOT/'packaging/windows/runtime-baseline.lock.json').read_text())
        self.assertRegex(baseline['sha256'],r'^[0-9a-f]{64}$')
        self.assertIn('/windows-v1.6-tatsunakyo.21-preview/',baseline['url'])


if __name__=='__main__':unittest.main()
