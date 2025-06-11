# File Structure Update Note

## 📁 Node-RED Flow File Relocation (2025-06-06)

### Change Description
To better organize the project structure, the Node-RED flow file was moved from the root directory to its corresponding service directory.

### File Move
```bash
# Before
flows/face_access_control.json

# After
services/node_red/face_access_control.json
```

### Updated Files

#### 1. `deployment/start_services.sh`
- **Update**: Flow file copy logic in the `start_nodered()` function.
- **Change**: Prioritizes finding the flow file in `services/node_red/`, with backward compatibility for the old path.
- **Added**: A warning message if the file cannot be found.

#### 2. `docker-compose.yml`
- **Removed**: The `./flows:/data/flows` volume mount.
- **Kept**: The `./services/node_red/data:/data` core data mount.
- **Simplified**: Node-RED configuration is now cleaner.

#### 3. `README.md`
- **Update**: Project structure description.
- **Change**: Reflects the new file organization.

#### 4. `docs/todo.md` (Previously `prompt/todo.md`)
- **Update**: Reference to the Node-RED flow directory.
- **Change**: `flows/` → `services/node_red/`.

#### 5. `docs/deployment_guide.md`
- **Update**: Instructions for importing the flow file.
- **Update**: Path references in the backup script section.

### New Directory Structure
```
services/node_red/
├── data/                           # Node-RED runtime data (Docker volume)
└── face_access_control.json       # Face recognition flow configuration file
```

### Deployment Impact
- ✅ **Backward Compatible**: The startup script checks both old and new locations.
- ✅ **No Manual Action Required**: The startup script handles file copying automatically.
- ✅ **Docker Config Simplified**: Reduced one volume mount.

### Advantages
1. **Clear Structure**: Each service's configuration files are in its own directory.
2. **Easier Maintenance**: All Node-RED related files are managed together.
3. **Reduced Clutter**: Fewer files in the root directory.
4. **Docker Optimization**: Simplified container configuration.

### Usage Instructions
```bash
# The script will automatically copy the flow file when starting services
./deployment/start_services.sh --with-nodered

# Manually copy the flow file (if needed)
cp services/node_red/face_access_control.json services/node_red/data/

# Import in Node-RED
# Visit http://localhost:1880
# Use the import function to load the flow file
```

### Notes
- The old `flows/` directory can be safely deleted.
- If you have custom flow files, please move them to the new location.
- The startup script handles path compatibility, so no changes are needed for that.

---

**Last Updated**: 2025-06-06
**Scope**: Deployment configuration and documentation
**Compatibility**: Fully backward compatible 