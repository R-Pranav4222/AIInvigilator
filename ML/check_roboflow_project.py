"""
Diagnostic script to check Roboflow project details
"""

from roboflow import Roboflow

API_KEY = "oL4YKGjfGLGDnovxVvcx"

print("🔍 Checking Roboflow API access...\n")

try:
    rf = Roboflow(api_key=API_KEY)
    print("✅ API key valid!\n")
    
    # Try to access the workspace
    print("📁 Checking workspace: research-xfm0x")
    workspace = rf.workspace("research-xfm0x")
    print("✅ Workspace accessible!\n")
    
    # Try to access the project
    print("📦 Checking project: major-aast-dataset-3d")
    project = workspace.project("major-aast-dataset-3d")
    print("✅ Project accessible!\n")
    
    print("📊 Project Details:")
    print(f"   Project ID: {project.id if hasattr(project, 'id') else 'N/A'}")
    print(f"   Project Name: {project.name if hasattr(project, 'name') else 'N/A'}")
    
    # Try to get versions
    print("\n🔍 Checking available versions...")
    available_versions = []
    for v in range(1, 11):  # Check versions 1-10
        try:
            version = project.version(v)
            available_versions.append(v)
            print(f"   ✅ Version {v} available")
        except Exception as e:
            pass
    
    if available_versions:
        print(f"\n✅ Found {len(available_versions)} version(s): {available_versions}")
        print(f"📥 You can download version {available_versions[-1]} (latest)")
    else:
        print("\n❌ No versions found!")
        print("\n💡 Possible issues:")
        print("   1. Project might be private (check sharing settings)")
        print("   2. Project name might be different")
        print("   3. API key might not have access to this project")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n💡 Troubleshooting:")
    print("1. Verify your API key at: https://app.roboflow.com/settings/api")
    print("2. Check project URL: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d")
    print("3. Make sure the project is public or you have access")
    print("4. Try copying the workspace/project name directly from the URL")
