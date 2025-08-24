# PHASE A7: Documentation Hygiene & Archive

**Objective**: Establish comprehensive documentation validation and drift prevention system

**Prerequisites**: Phase A6 complete (Gateway operational with complete event ingestion pipeline)

---

## 🎯 **Goals**

### **Primary**
- Implement automated documentation consistency validation
- Create CI gates to prevent documentation drift
- Establish comprehensive broken link detection
- Add automated orphaned file detection and cleanup

### **Non-Goals**
- Content creation (documentation should be complete from previous phases)
- Major structural changes (foundation established in Phase A0)
- Performance optimization (focus on correctness)

---

## 📋 **Deliverables**

### **1. Documentation Hygiene Checker** (`scripts/docs-hygiene.py`)
```python
#!/usr/bin/env python3
"""
Comprehensive documentation hygiene checker for V2
Detects inconsistencies, broken links, and orphaned files
"""

import os
import re
import json
import yaml
from pathlib import Path
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import requests
from urllib.parse import urljoin

@dataclass
class HygieneIssue:
    """Documentation hygiene issue"""
    file_path: str
    line_number: int
    issue_type: str
    description: str
    severity: str  # 'error', 'warning', 'info'

class DocumentationHygienist:
    """Comprehensive documentation hygiene checker"""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.issues: List[HygieneIssue] = []
        
    def check_all(self) -> List[HygieneIssue]:
        """Run all hygiene checks"""
        self.issues = []
        
        print("🔍 Running documentation hygiene checks...")
        
        # Core checks
        self._check_v1_artifacts()
        self._check_broken_internal_links()
        self._check_orphaned_files()
        self._check_openapi_consistency()
        self._check_roadmap_drift()
        self._check_example_validity()
        self._check_file_freshness()
        
        return self.issues
    
    def _check_v1_artifacts(self):
        """Check for V1 artifacts in active documentation"""
        print("  Checking for V1 artifacts...")
        
        v1_patterns = [
            r'\brl_\w+',           # V1 relational schema
            r'\bsl_\w+',           # V1 semantic schema  
            r'\bgraph_\w+',        # V1 graph schema
            r'\bPhase [0-9]+\b',   # V1 phase numbering
            r'\bphase-[0-9]+',     # V1 phase files
            r'\bBUILD_MODE\b',     # V1 terminology
            r'\bpost-phase\b',     # V1 terminology
        ]
        
        for doc_file in self._get_active_docs():
            content = doc_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for pattern in v1_patterns:
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        self.issues.append(HygieneIssue(
                            file_path=str(doc_file.relative_to(self.repo_root)),
                            line_number=line_num,
                            issue_type="v1_artifact",
                            description=f"V1 artifact detected: '{match.group()}'",
                            severity="error"
                        ))
    
    def _check_broken_internal_links(self):
        """Check for broken internal links in documentation"""
        print("  Checking internal links...")
        
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        
        for doc_file in self._get_active_docs():
            content = doc_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                matches = re.finditer(link_pattern, line)
                for match in matches:
                    link_text, link_url = match.groups()
                    
                    # Skip external links
                    if link_url.startswith(('http://', 'https://', 'mailto:')):
                        continue
                    
                    # Check internal file links
                    if link_url.startswith('#'):
                        # Anchor link - check if target exists in same file
                        self._check_anchor_link(doc_file, link_url, line_num)
                    else:
                        # File link - check if target file exists
                        self._check_file_link(doc_file, link_url, line_num)
    
    def _check_file_link(self, source_file: Path, link_url: str, line_num: int):
        """Check if linked file exists"""
        # Remove anchor part
        file_part = link_url.split('#')[0]
        
        # Resolve relative path
        if file_part.startswith('/'):
            # Absolute path from repo root
            target_path = self.repo_root / file_part.lstrip('/')
        else:
            # Relative path from source file
            target_path = (source_file.parent / file_part).resolve()
        
        if not target_path.exists():
            self.issues.append(HygieneIssue(
                file_path=str(source_file.relative_to(self.repo_root)),
                line_number=line_num,
                issue_type="broken_link",
                description=f"Broken link to: {link_url}",
                severity="error"
            ))
    
    def _check_orphaned_files(self):
        """Check for orphaned documentation files"""
        print("  Checking for orphaned files...")
        
        # Get all documentation files
        all_docs = set(self._get_active_docs())
        referenced_files = set()
        
        # Find all file references in documentation
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        
        for doc_file in all_docs:
            content = doc_file.read_text(encoding='utf-8')
            matches = re.finditer(link_pattern, content)
            
            for match in matches:
                link_url = match.group(2)
                
                # Skip external links and anchors
                if (link_url.startswith(('http://', 'https://', 'mailto:', '#'))):
                    continue
                
                # Resolve file reference
                file_part = link_url.split('#')[0]
                if file_part.startswith('/'):
                    target_path = self.repo_root / file_part.lstrip('/')
                else:
                    target_path = (doc_file.parent / file_part).resolve()
                
                if target_path.exists() and target_path.suffix == '.md':
                    referenced_files.add(target_path)
        
        # Find orphaned files (not referenced and not index files)
        index_files = {'README.md', 'INDEX.md', 'ONBOARD.md'}
        
        for doc_file in all_docs:
            if (doc_file not in referenced_files and 
                doc_file.name not in index_files):
                self.issues.append(HygieneIssue(
                    file_path=str(doc_file.relative_to(self.repo_root)),
                    line_number=1,
                    issue_type="orphaned_file",
                    description="File is not referenced by any other documentation",
                    severity="warning"
                ))
    
    def _check_openapi_consistency(self):
        """Check OpenAPI ↔ api.md consistency"""
        print("  Checking OpenAPI consistency...")
        
        openapi_file = self.repo_root / 'docs' / 'openapi.yaml'
        api_md_file = self.repo_root / 'docs' / 'api.md'
        
        if not openapi_file.exists() or not api_md_file.exists():
            return
        
        # Load OpenAPI spec
        with open(openapi_file) as f:
            openapi_spec = yaml.safe_load(f)
        
        # Get all paths from OpenAPI
        openapi_paths = set(openapi_spec.get('paths', {}).keys())
        
        # Find endpoint references in api.md
        api_content = api_md_file.read_text(encoding='utf-8')
        endpoint_pattern = r'### (GET|POST|PUT|DELETE|PATCH) (/[^\s]+)'
        api_endpoints = set()
        
        for match in re.finditer(endpoint_pattern, api_content):
            method, path = match.groups()
            api_endpoints.add(path)
        
        # Check for mismatches
        missing_in_api = openapi_paths - api_endpoints
        missing_in_openapi = api_endpoints - openapi_paths
        
        for path in missing_in_api:
            self.issues.append(HygieneIssue(
                file_path="docs/api.md",
                line_number=1,
                issue_type="openapi_mismatch",
                description=f"Endpoint {path} exists in OpenAPI but not documented in api.md",
                severity="error"
            ))
        
        for path in missing_in_openapi:
            self.issues.append(HygieneIssue(
                file_path="docs/openapi.yaml",
                line_number=1,
                issue_type="openapi_mismatch", 
                description=f"Endpoint {path} documented in api.md but missing from OpenAPI",
                severity="error"
            ))
    
    def _check_roadmap_drift(self):
        """Check for roadmap vs implementation drift"""
        print("  Checking roadmap drift...")
        
        roadmap_file = self.repo_root / 'docs' / 'v2_roadmap.md'
        if not roadmap_file.exists():
            return
            
        content = roadmap_file.read_text(encoding='utf-8')
        
        # Check for outdated status markers
        outdated_patterns = [
            r'status:\s*pending',
            r'TODO:',
            r'FIXME:',
            r'placeholder',
        ]
        
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern in outdated_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.issues.append(HygieneIssue(
                        file_path="docs/v2_roadmap.md",
                        line_number=line_num,
                        issue_type="roadmap_drift",
                        description=f"Potentially outdated content: {line.strip()}",
                        severity="warning"
                    ))
    
    def _check_file_freshness(self):
        """Check for files that haven't been updated recently"""
        print("  Checking file freshness...")
        
        import datetime
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=90)
        
        for doc_file in self._get_active_docs():
            mtime = datetime.datetime.fromtimestamp(doc_file.stat().st_mtime)
            
            if mtime < cutoff_date:
                self.issues.append(HygieneIssue(
                    file_path=str(doc_file.relative_to(self.repo_root)),
                    line_number=1,
                    issue_type="stale_file",
                    description=f"File hasn't been updated since {mtime.strftime('%Y-%m-%d')}",
                    severity="info"
                ))
    
    def _get_active_docs(self) -> List[Path]:
        """Get all active documentation files (excluding archive)"""
        docs_dir = self.repo_root / 'docs'
        active_docs = []
        
        for file_path in docs_dir.rglob('*.md'):
            # Skip archived content
            if 'archive' in str(file_path).lower():
                continue
            active_docs.append(file_path)
        
        # Include root documentation
        for file_name in ['README.md', 'CONTRIBUTING.md', 'SECURITY.md']:
            file_path = self.repo_root / file_name
            if file_path.exists():
                active_docs.append(file_path)
        
        return active_docs

def main():
    """Main entry point for documentation hygiene check"""
    repo_root = Path(__file__).parent.parent
    hygienist = DocumentationHygienist(repo_root)
    
    issues = hygienist.check_all()
    
    # Group issues by severity
    errors = [i for i in issues if i.severity == 'error']
    warnings = [i for i in issues if i.severity == 'warning']
    info = [i for i in issues if i.severity == 'info']
    
    # Print results
    print(f"\n📊 Documentation Hygiene Results:")
    print(f"  🔴 Errors: {len(errors)}")
    print(f"  🟡 Warnings: {len(warnings)}")
    print(f"  ℹ️  Info: {len(info)}")
    
    # Print detailed issues
    for issue in errors:
        print(f"\n🔴 ERROR: {issue.file_path}:{issue.line_number}")
        print(f"   {issue.description}")
    
    for issue in warnings:
        print(f"\n🟡 WARNING: {issue.file_path}:{issue.line_number}")
        print(f"   {issue.description}")
    
    # Return exit code based on errors
    return 1 if errors else 0

if __name__ == "__main__":
    exit(main())
```

### **2. CI Documentation Gate** (`.github/workflows/docs-hygiene.yml`)
```yaml
name: Documentation Hygiene

on:
  push:
    branches: [ main, develop ]
    paths: 
      - 'docs/**'
      - '*.md'
      - 'siren/**'
  pull_request:
    branches: [ main ]
    paths:
      - 'docs/**'
      - '*.md' 
      - 'siren/**'

jobs:
  docs-hygiene:
    runs-on: ubuntu-latest
    name: Documentation Validation
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install pyyaml requests
    
    - name: Run documentation hygiene checks
      run: |
        python scripts/docs-hygiene.py
    
    - name: Validate OpenAPI syntax
      run: |
        python -c "import yaml; yaml.safe_load(open('docs/openapi.yaml'))"
    
    - name: Check for duplicate OpenAPI paths
      run: |
        grep -E "^\s*/v1/" docs/openapi.yaml | sort | uniq -d | head -1 && exit 1 || echo "✅ No duplicate paths"
    
    - name: Run API example validation
      run: |
        python -m siren.validators.check_api_examples
    
    - name: Run event schema validation  
      run: |
        python -m siren.validators.check_event_schema
    
    - name: Run banned phrases check
      run: |
        python -m siren.validators.check_banned_phrases
    
    - name: Generate hygiene report
      if: always()
      run: |
        echo "## 📋 Documentation Hygiene Report" >> $GITHUB_STEP_SUMMARY
        python scripts/docs-hygiene.py --format github >> $GITHUB_STEP_SUMMARY
```

### **3. Enhanced Makefile Targets**
```makefile
# Documentation hygiene and validation targets

docs:scrub:
	@echo "🧹 Running comprehensive documentation hygiene check..."
	@python scripts/docs-hygiene.py || (echo "❌ Documentation hygiene failed" && exit 1)
	@echo "✅ Documentation hygiene passed"

docs:check-deep:
	@echo "🔍 Running deep documentation validation..."
	@python scripts/docs-hygiene.py
	@python -m siren.validators.check_api_examples
	@python -m siren.validators.check_event_schema  
	@python -m siren.validators.check_migration_parity
	@python -m siren.validators.check_banned_phrases
	@echo "✅ Deep validation completed"

docs:orphan-check:
	@echo "🔍 Checking for orphaned documentation files..."
	@python scripts/docs-hygiene.py --check orphaned_files
	@echo "✅ Orphan check completed"

docs:link-check:
	@echo "🔗 Checking all internal links..."
	@python scripts/docs-hygiene.py --check broken_links
	@echo "✅ Link check completed"

docs:freshness:
	@echo "📅 Checking documentation freshness..."
	@python scripts/docs-hygiene.py --check file_freshness
	@echo "✅ Freshness check completed"

docs:archive-scan:
	@echo "🗂️ Scanning for V1 artifacts in active documentation..."
	@python scripts/docs-hygiene.py --check v1_artifacts
	@echo "✅ Archive scan completed"

# CI-ready comprehensive gate
docs:doclint:
	@echo "🚪 Running CI documentation lint gate..."
	make docs:check-deep
	make openapi:validate
	@echo "✅ All documentation validation passed - ready for CI"
```

### **4. Link Checker Enhancement** (`scripts/check-broken-links.sh`)
```bash
#!/bin/bash
# Comprehensive broken link checker

set -e

echo "🔗 Checking for broken links in documentation..."

# Function to check if URL is accessible
check_url() {
    local url="$1"
    if curl --output /dev/null --silent --head --fail "$url"; then
        return 0
    else
        return 1
    fi
}

# Find all markdown files (excluding archives)
find docs/ -name "*.md" -not -path "*/archive*" | while read -r file; do
    echo "Checking $file..."
    
    # Extract all markdown links
    grep -oP '\[([^\]]+)\]\(([^)]+)\)' "$file" | while read -r link; do
        # Extract URL from markdown link syntax
        url=$(echo "$link" | sed -n 's/.*](\([^)]*\)).*/\1/p')
        
        # Skip anchors and relative links
        if [[ "$url" =~ ^# ]] || [[ ! "$url" =~ ^https?:// ]]; then
            continue
        fi
        
        # Check external URL
        if ! check_url "$url"; then
            echo "❌ Broken link in $file: $url"
            exit 1
        fi
    done
done

echo "✅ All external links are accessible"
```

### **5. Documentation Metrics** (`scripts/docs-metrics.py`)
```python
#!/usr/bin/env python3
"""
Generate documentation quality metrics for monitoring
"""

import json
from pathlib import Path
from typing import Dict, Any
import datetime

def generate_docs_metrics() -> Dict[str, Any]:
    """Generate comprehensive documentation metrics"""
    
    repo_root = Path(__file__).parent.parent
    docs_dir = repo_root / 'docs'
    
    metrics = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'total_files': 0,
        'total_lines': 0,
        'total_words': 0,
        'files_by_type': {},
        'staleness_days': {},
        'link_count': 0,
        'coverage': {}
    }
    
    # Analyze all documentation files
    for file_path in docs_dir.rglob('*.md'):
        if 'archive' in str(file_path):
            continue
            
        metrics['total_files'] += 1
        
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        words = content.split()
        
        metrics['total_lines'] += len(lines)
        metrics['total_words'] += len(words)
        
        # File type classification
        file_type = classify_doc_type(file_path.name, content)
        metrics['files_by_type'][file_type] = metrics['files_by_type'].get(file_type, 0) + 1
        
        # Staleness calculation
        mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
        staleness = (datetime.datetime.now() - mtime).days
        metrics['staleness_days'][str(file_path.relative_to(repo_root))] = staleness
        
        # Link counting
        import re
        link_count = len(re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content))
        metrics['link_count'] += link_count
    
    # Coverage analysis
    metrics['coverage'] = analyze_coverage(repo_root)
    
    return metrics

def classify_doc_type(filename: str, content: str) -> str:
    """Classify documentation file type"""
    if 'api' in filename.lower():
        return 'api'
    elif 'architecture' in filename.lower():
        return 'architecture'
    elif 'roadmap' in filename.lower():
        return 'roadmap'
    elif 'phase' in filename.lower():
        return 'phase_prompt'
    elif 'test' in filename.lower():
        return 'testing'
    elif filename.lower().startswith('readme'):
        return 'readme'
    else:
        return 'other'

def analyze_coverage(repo_root: Path) -> Dict[str, Any]:
    """Analyze documentation coverage"""
    
    # Check for required documentation files
    required_files = [
        'docs/architecture.md',
        'docs/api.md', 
        'docs/openapi.yaml',
        'docs/v2_roadmap.md',
        'docs/development-workflow.md',
        'README.md'
    ]
    
    coverage = {
        'required_files_present': 0,
        'required_files_total': len(required_files),
        'missing_files': []
    }
    
    for required_file in required_files:
        file_path = repo_root / required_file
        if file_path.exists():
            coverage['required_files_present'] += 1
        else:
            coverage['missing_files'].append(required_file)
    
    coverage['completeness_percentage'] = (
        coverage['required_files_present'] / coverage['required_files_total'] * 100
    )
    
    return coverage

def main():
    """Generate and output documentation metrics"""
    metrics = generate_docs_metrics()
    
    print("📊 Documentation Quality Metrics")
    print("=" * 40)
    print(f"Total Files: {metrics['total_files']}")
    print(f"Total Lines: {metrics['total_lines']:,}")
    print(f"Total Words: {metrics['total_words']:,}")
    print(f"Total Links: {metrics['link_count']}")
    print(f"Coverage: {metrics['coverage']['completeness_percentage']:.1f}%")
    print()
    
    # File type breakdown
    print("File Types:")
    for file_type, count in metrics['files_by_type'].items():
        print(f"  {file_type}: {count}")
    print()
    
    # Staleness report
    stale_files = [(f, days) for f, days in metrics['staleness_days'].items() if days > 30]
    if stale_files:
        print("⚠️  Stale Files (>30 days):")
        for file_path, days in sorted(stale_files, key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {file_path}: {days} days")
    else:
        print("✅ No stale files detected")
    
    # Save metrics as JSON for CI
    metrics_file = Path(__file__).parent.parent / 'docs-metrics.json'
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    return 0

if __name__ == "__main__":
    exit(main())
```

---

## ✅ **Acceptance Criteria**

### **Hygiene Detection**
- [ ] All V1 artifacts detected in active documentation
- [ ] Broken internal links identified with line numbers
- [ ] Orphaned files flagged for cleanup or integration
- [ ] OpenAPI ↔ api.md consistency validated

### **CI Integration**
- [ ] Documentation hygiene gate blocks PR merges on errors
- [ ] All existing validation tools integrated into single gate
- [ ] GitHub Actions workflow runs on documentation changes
- [ ] Clear error reporting with actionable feedback

### **Automation**
- [ ] Makefile targets provide granular hygiene checking
- [ ] Scripts handle edge cases and provide clear output
- [ ] Metrics generation tracks documentation quality over time
- [ ] Link checking validates external URL accessibility

### **Quality Assurance**
- [ ] Zero false positives in hygiene checks
- [ ] Comprehensive coverage of common documentation issues
- [ ] Performance acceptable for CI environments
- [ ] Clear distinction between errors, warnings, and info

---

## 🚧 **Implementation Steps**

### **Step 1: Core Hygiene Checker**
1. Implement DocumentationHygienist with comprehensive checks
2. Add V1 artifact detection with pattern matching
3. Create broken link detection for internal references
4. Test with current documentation for baseline

### **Step 2: CI Integration**
1. Create GitHub Actions workflow for documentation validation
2. Integrate all existing validators into single gate
3. Add clear error reporting and GitHub step summaries
4. Test with pull request simulation

### **Step 3: Enhanced Makefile Targets**
1. Add granular documentation checking targets
2. Create comprehensive `docs:doclint` gate
3. Add utility targets for specific issue types
4. Test integration with existing development workflow

### **Step 4: Metrics and Monitoring**
1. Implement documentation quality metrics generation
2. Add staleness tracking and coverage analysis
3. Create broken link checker for external URLs
4. Test metrics accuracy and usefulness

---

## 🔧 **Technical Decisions**

### **Issue Classification**
- **Errors**: Block CI, must be fixed before merge
- **Warnings**: Don't block CI, should be addressed
- **Info**: Informational only, track for trends

### **Validation Scope**
- **Active Documentation**: All files in docs/ excluding archives
- **Repository Root**: README, CONTRIBUTING, SECURITY files
- **Siren Directory**: Development tracking and prompts

### **CI Gate Strategy**
- **Fast Feedback**: Run on documentation path changes only
- **Comprehensive**: Include all existing validators
- **Clear Output**: GitHub step summaries for PR visibility

---

## 🚨 **Risks & Mitigations**

### **False Positives**
- **Risk**: Hygiene checker flags valid content as problematic
- **Mitigation**: Comprehensive testing, clear exemption patterns

### **CI Performance**
- **Risk**: Documentation validation slows down CI significantly
- **Mitigation**: Optimize checkers, run only on relevant changes

### **Maintenance Burden**
- **Risk**: Hygiene checks become difficult to maintain
- **Mitigation**: Simple, well-tested code with clear patterns

---

## 📊 **Success Metrics**

- **Detection Accuracy**: 100% of known issues caught by checkers
- **False Positive Rate**: < 5% of flagged issues are invalid
- **CI Performance**: < 2 minutes for complete documentation validation
- **Developer Satisfaction**: Clear, actionable feedback on documentation issues

---

## 🔄 **Next Phase**

**Phase A7 completes the V2 Foundation (Phase A)**

**Next: Phase B**: V2 Contracts Implementation
- Multi-lens search implementations
- Administrative endpoints
- GraphAdapter interface implementations
- Performance optimization

**Foundation Achievement**: Phase A provides complete, reliable foundation with comprehensive quality gates for V2 development
