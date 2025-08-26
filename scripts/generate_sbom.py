#!/usr/bin/env python3
"""
Generate Software Bill of Materials (SBOM) for MNX
Creates SBOM artifacts for security and compliance tracking
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

def run_command(cmd: List[str], cwd: str = None) -> tuple[str, int]:
    """Run a command and return output and exit code"""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=cwd,
            timeout=60
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", 1
    except Exception as e:
        return f"Command failed: {e}", 1

def get_python_dependencies() -> List[Dict[str, Any]]:
    """Get Python dependencies from requirements.txt"""
    components = []
    
    requirements_files = [
        "requirements.txt",
        "services/gateway/requirements.txt",
        "services/publisher/requirements.txt", 
        "services/search/requirements.txt",
        "projectors/sdk/requirements.txt",
        "projectors/relational/requirements.txt",
        "projectors/semantic/requirements.txt",
        "projectors/graph/requirements.txt",
        "projectors/translator_memory_to_emo/requirements.txt"
    ]
    
    for req_file in requirements_files:
        if os.path.exists(req_file):
            try:
                with open(req_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse package==version format
                            if '==' in line:
                                name, version = line.split('==', 1)
                            elif '>=' in line:
                                name, version = line.split('>=', 1)
                                version = f">={version}"
                            else:
                                name, version = line, "latest"
                            
                            components.append({
                                "type": "library",
                                "bom-ref": f"python-{name}-{version}",
                                "name": name,
                                "version": version,
                                "purl": f"pkg:pypi/{name}@{version}",
                                "scope": "required",
                                "properties": [
                                    {"name": "source_file", "value": req_file}
                                ]
                            })
            except Exception as e:
                print(f"Warning: Could not parse {req_file}: {e}")
    
    return components

def get_docker_images() -> List[Dict[str, Any]]:
    """Get Docker images from compose files"""
    components = []
    
    compose_files = [
        "infra/docker-compose.yml",
        "infra/docker-compose-production.yml", 
        "infra/docker-compose-emo.yml"
    ]
    
    # Known base images from Dockerfiles
    base_images = [
        {"name": "python", "version": "3.11-slim", "source": "gateway/publisher/search"},
        {"name": "pgvector/pgvector", "version": "pg16", "source": "postgres-age"},
        {"name": "prom/prometheus", "version": "latest", "source": "monitoring"}
    ]
    
    for image in base_images:
        components.append({
            "type": "container",
            "bom-ref": f"docker-{image['name']}-{image['version']}",
            "name": image["name"],
            "version": image["version"],
            "purl": f"pkg:docker/{image['name']}@{image['version']}",
            "scope": "required",
            "properties": [
                {"name": "source", "value": image["source"]}
            ]
        })
    
    return components

def get_system_info() -> Dict[str, Any]:
    """Get system and build information"""
    
    # Get git commit
    git_commit, _ = run_command(["git", "rev-parse", "HEAD"])
    git_commit = git_commit.strip()
    
    # Get git branch
    git_branch, _ = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    git_branch = git_branch.strip()
    
    return {
        "git_commit": git_commit,
        "git_branch": git_branch,
        "build_time": datetime.utcnow().isoformat() + "Z",
        "python_version": sys.version,
        "platform": sys.platform
    }

def generate_cyclonedx_sbom() -> Dict[str, Any]:
    """Generate SBOM in CycloneDX format"""
    
    # Get components
    python_deps = get_python_dependencies()
    docker_images = get_docker_images()
    system_info = get_system_info()
    
    # Create CycloneDX SBOM
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{system_info['git_commit'][:8]}-{datetime.utcnow().strftime('%Y%m%d')}",
        "version": 1,
        "metadata": {
            "timestamp": system_info["build_time"],
            "tools": [
                {
                    "vendor": "MNX",
                    "name": "generate_sbom.py",
                    "version": "1.0.0"
                }
            ],
            "component": {
                "type": "application",
                "bom-ref": "mnx-main",
                "name": "MnemonicNexus",
                "version": f"alpha-s0-{system_info['git_commit'][:8]}",
                "description": "Event-sourced system with multi-lens projections",
                "properties": [
                    {"name": "git_commit", "value": system_info["git_commit"]},
                    {"name": "git_branch", "value": system_info["git_branch"]},
                    {"name": "build_time", "value": system_info["build_time"]},
                    {"name": "python_version", "value": system_info["python_version"]},
                    {"name": "platform", "value": system_info["platform"]}
                ]
            }
        },
        "components": python_deps + docker_images
    }
    
    return sbom

def generate_spdx_sbom() -> Dict[str, Any]:
    """Generate SBOM in SPDX format"""
    system_info = get_system_info()
    
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "MnemonicNexus-SBOM",
        "documentNamespace": f"https://github.com/your-org/mneumonicnexus/sbom/{system_info['git_commit']}",
        "creators": ["Tool: generate_sbom.py"],
        "created": system_info["build_time"],
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-MNX",
                "name": "MnemonicNexus",
                "downloadLocation": "https://github.com/your-org/mneumonicnexus",
                "filesAnalyzed": False,
                "copyright": "NOASSERTION",
                "versionInfo": f"alpha-s0-{system_info['git_commit'][:8]}"
            }
        ]
    }
    
    return sbom

def main():
    """Main SBOM generation function"""
    print("🔍 Generating Software Bill of Materials (SBOM)...")
    
    # Create artifacts directory
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    # Generate CycloneDX SBOM
    print("📋 Generating CycloneDX SBOM...")
    cyclonedx_sbom = generate_cyclonedx_sbom()
    
    cyclonedx_file = artifacts_dir / "sbom-cyclonedx.json"
    with open(cyclonedx_file, 'w') as f:
        json.dump(cyclonedx_sbom, f, indent=2)
    
    print(f"✅ CycloneDX SBOM written to {cyclonedx_file}")
    
    # Generate SPDX SBOM
    print("📋 Generating SPDX SBOM...")
    spdx_sbom = generate_spdx_sbom()
    
    spdx_file = artifacts_dir / "sbom-spdx.json"
    with open(spdx_file, 'w') as f:
        json.dump(spdx_sbom, f, indent=2)
    
    print(f"✅ SPDX SBOM written to {spdx_file}")
    
    # Generate summary
    total_components = len(cyclonedx_sbom.get("components", []))
    python_components = len([c for c in cyclonedx_sbom.get("components", []) if c["type"] == "library"])
    docker_components = len([c for c in cyclonedx_sbom.get("components", []) if c["type"] == "container"])
    
    print("\n📊 SBOM Summary:")
    print(f"   Total components: {total_components}")
    print(f"   Python packages: {python_components}")
    print(f"   Docker images: {docker_components}")
    print(f"   Git commit: {cyclonedx_sbom['metadata']['component']['properties'][0]['value'][:8]}")
    print(f"   Build time: {cyclonedx_sbom['metadata']['timestamp']}")
    
    print("\n💡 SBOM files generated successfully!")
    print("   Use these for security scanning, compliance, and supply chain analysis")

if __name__ == "__main__":
    main()
