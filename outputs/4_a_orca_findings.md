SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/plugin_system
EXCERPTS:
> Capabilities, not single-purpose plugins - one plugin is a package that registers one or more capabilities, each a typed unit of functionality (e.g. post-processing, script, printer-connection). Each capability type has a fixed C++ entry point and is invoked at a specific place in the app; a plugin's "types" are simply the set of capability types it registers.
>
> A permission boundary, not a sandbox - filesystem, network, process-spawn, and thread-creation operations by plugin code are categorized and gated by an audit hook that prompts the user and remembers the answer per plugin; a plugin can also declare what it expects up front with orca.request_permissions(...). See the audit doc for current scope and gaps.
>
> | Capability type | Entry method | Invoked by
> | slicing-pipeline | execute(ctx) | Print at configured slicing steps, and PostProcessor at psGCodePostProcess during G-code export
> | script | execute() | the Plugins dialog -> Run action
> | printer-connection | agent methods | NetworkAgentFactory, registered through a loader on-capability-load callback wired in GUI_App
> | pages | get_ui(), on_message() | PluginPages (plugin/host/PluginPages.cpp), which adds a main-window tab per enabled capability from the on-capability-load callbacks
>
> Independently of type, every loaded and enabled capability receives application lifecycle events through on_lifecycle_event(event, ctx). Call sites in libslic3r and the GUI raise them with Slic3r::fire_lifecycle_event() (libslic3r/LifecycleEvents.hpp); plugin_hooks installs the dispatcher, which forwards to PluginManager::dispatch_lifecycle_event() synchronously on the raising thread, skips the remaining capabilities once a slice is cancelled, and logs and swallows handler exceptions.
>
> A plugin is a folder under one of two roots, containing a single entry file:
> | Root | Source
> | data_dir()/orca_plugins/ | locally installed / side-loaded
> | data_dir()/orca_plugins/_subscribed/<user_id>/ | cloud-subscribed (per logged-in user)
> The entry file is either a single .py file (metadata in a PEP 723 comment block) or a .whl wheel (metadata from the wheel's METADATA). The capabilities the plugin registers determine which workflows can run it; there is no separate type declaration in the metadata.
>
> 4. PluginLoader::load_plugin()  (worker thread, serialized)
>         │   ├─ install dependencies via bundled `uv`; extract bundled .whl deps onto sys.path
>         │   ├─ begin capture → import module (runs @orca.plugin, marking the package class)
>         │   ├─ finalize capture → instantiate package, call register_capabilities(),
>         │   │      collect its request_permissions() declarations
>         │   ├─ if permissions were declared, show one combined dialog;
>         │   │      a No aborts the load before any capability is created
>         │   ├─ instantiate each registered capability and cache its get_name()
>         │   ├─ set_audit_plugin_key(descriptor.plugin_key)   // audit identity
>         │   ├─ on_load()  (under the GIL)
>         │   └─ store the capabilities; fire on-load + on-capability-load callbacks
>
> Each entry is a single string with three ;-separated fields:
> <plugin_name>;<cloud_uuid>;<capability_name>
> {
>   "plugins": [
>     "Sample Plugin;1f998ea9-0183-4cc5-957f-4eef659ba4e6;G-code Benchmark (.py)",
>     "master_plugin;;header-stamp"
>   ],
>   "post_process_plugin": ["G-code Benchmark (.py)", "header-stamp"]
> }

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/plugin_development
EXCERPTS:
> #### 1. The metadata block (PEP 723)
> OrcaSlicer reads identity and dependency metadata from a PEP 723 inline script metadata block: a comment block delimited by # /// script and # ///, with each content line prefixed by #. Identity fields live in a [tool.orcaslicer.plugin] table; dependency fields live at the TOML root. Parsing is implemented in PythonFileUtils.cpp::parse_pep723_toml / read_python_plugin_metadata.
>
> # /// script
> # requires-python = ">=3.12"
> # dependencies = []
> #
> # [tool.orcaslicer.plugin]
> # name = "Sample Plugin"
> # description = "Appends a short build-environment note to the exported G-code."
> # author = "Your Name"
> # version = "1.0.0"
> # ///
>
> | Field | Location | Required | Notes
> | name | [tool.orcaslicer.plugin] | recommended | display name in the Plugins dialog
> | description | [tool.orcaslicer.plugin] | recommended | shown in the plugin Description tab
> | author | [tool.orcaslicer.plugin] | optional |
> | version | [tool.orcaslicer.plugin] | recommended |
> | dependencies | TOML root | optional | array of pip requirements (see Dependencies)
> | requires-python | TOML root | optional | read but not stored or enforced against the bundled interpreter today
>
> The metadata block no longer declares a type. A plugin's type(s) are derived from the capability classes it registers (each capability's get_type()), so the same metadata block is used whether the plugin offers one capability or several. The PEP 723 parser (parse_pep723_toml) reads only name, description, author, version, requires-python, and dependencies; any other key (including a stray type = ...) is ignored.
>
> | Symbol | Kind | Members / purpose
> | orca.PluginType | enum | PrinterConnection, Pages, Analysis, Importer, Exporter, Visualization, Script, SlicingPipeline, ResourceTexture, Unknown
> | orca.PluginResult | enum | Success, Skipped, RecoverableError, FatalError
> | orca.PluginContext | class | base context, field orca_version: str
> | orca.ExecutionResult | class | fields status, message, data; factories below
> | orca.PythonPluginBase | class | the root capability base; subclasses must implement get_name()
> | orca.base | class | the package base; subclass it and override register_capabilities()
> | orca.plugin | decorator | marks the single package class for the file (exactly one per file)
> | orca.register_capability(cls) | function | register one capability class; call it inside register_capabilities()
> | orca.request_permissions(...) | function | declare filesystem, network, process, and thread permissions up front
>
> orca.ExecutionResult.success(message="", data="")
> orca.ExecutionResult.skipped(message="")
> orca.ExecutionResult.failure(status, message, data="")   # status is an orca.PluginResult
>
> | Method | Purpose
> | has_config_ui() -> bool | Return True to use the custom UI returned by get_config_ui() instead of the JSON editor.
> | get_config_ui() -> str | Return a self-contained HTML string. An empty or failing result falls back to the JSON editor.
> | get_default_config() -> str | Override the method to return a Python dict; OrcaSlicer exposes the resulting JSON as a string and uses it when the user restores global defaults. Without an override, the default is {}.
> | get_config() -> str | Return this capability's effective stored configuration as a JSON string. It is {} when no configuration has been saved.
> | get_config_version() -> str | Return the plugin version that last saved the configuration.
> | save_config(config: str) -> bool | Persist a JSON string for this capability. Use json.dumps(config_dict) and check the return value.
>
> | Base class | get_type() returns | Required methods | Invoked by
> | orca.script.ScriptPluginCapabilityBase | Script | get_name(), execute(self) -> ExecutionResult | the Plugins dialog -> Run action
> | orca.pages.PagesPluginCapabilityBase | Pages | get_name(), get_ui(self) -> str | a main-window tab added while the capability is enabled
> | orca.slicing.SlicingPipelineCapabilityBase | SlicingPipeline | get_name(), execute(self, ctx) -> ExecutionResult | configured slicing steps and G-code export / post-processing
> | orca.printer_agent.PrinterAgentBase | PrinterConnection | get_name() + ~30 agent methods (get_agent_info, connect_printer, ...) | the network / printer-agent layer on load
> | orca.resource_texture.ResourceTexturePluginCapabilityBase | ResourceTexture | get_name(), get_texture_dir(self) -> str | OrcaSlicer, when the capability is materialized
>
> Every capability must implement get_name(self) -> str. Lifecycle hooks on_load() / on_unload() are optional and available on every capability (defaults do nothing). Any capability can also override on_lifecycle_event(event, ctx) to observe application events
>
> The slicing context (orca.slicing.SlicingPipelineContext) is passed to execute and exposes the live slicing graph during geometry steps. At Step.psGCodePostProcess, the graph fields are None and the context instead exposes the working G-code file:
> | Field | Meaning
> | orca_version | OrcaSlicer version string (inherited from PluginContext)
> | step | the pipeline step currently being executed
> | print | the live print graph, or None at psGCodePostProcess
> | object | the current print object for object-scoped steps, or None
> | gcode_path | the working G-code path, set at psGCodePostProcess
> | host | target host, when exporting to a network printer
> | output_name | the output file name
> | config_value(key) | the resolved print configuration value, or None if absent
> | cancelled() | whether the active print has been cancelled
>
> Filesystem, network, process, and thread-creation access are audited. While execute() runs, a sensitive operation (a file read/write/create/delete, an HTTP/socket connection, spawning a process, or starting a thread) prompts the user with a Yes/No dialog naming the target; a "Yes" is remembered for that plugin so the same target does not prompt again. Thread creation is granted once per plugin: the work the spawned thread then runs is not audited. An operation inside a pre-determined allowed folder — data_dir(), the read-only resources_dir(), or (at psGCodePostProcess) the current G-code file's folder — needs no prompt at all
>
> #### 3. Registration
> The package - exactly one class per file is decorated with @orca.plugin and subclasses orca.base. Its register_capabilities(self) method calls orca.register_capability(Cls) once for each capability class you want to expose:
> @orca.plugin
> class SamplePlugin(orca.base):
>     def register_capabilities(self):
>         orca.request_permissions(
>             fs_read=["/path/to/input"],
>             network_http=["https://example.com"])
>         orca.register_capability(GCodeBenchmark)
>         orca.register_capability(EnvironmentReport)
>
> ### Dependencies
> List third-party requirements in the PEP 723 root dependencies array. On install, OrcaSlicer resolves them with a bundled uv into the plugin's environment (PluginLoader.cpp):
> # dependencies = ["requests==2.32.3", "humanize"]
> Keep dependencies minimal. Every dependency is code that runs under the same audit policy as your plugin and must be fetched at install time.
>
> ### Complete Examples (multi-capability; G-code post-process at export seam)
> class EnvironmentReport(orca.slicing.SlicingPipelineCapabilityBase):
>     def get_name(self):
>         return "Environment Report"
>
>     def execute(self, ctx):
>         # Post-process the exported file at the dedicated pipeline seam.
>         if ctx.step != orca.slicing.Step.psGCodePostProcess:
>             return orca.ExecutionResult.success()
>         try:
>             with open(ctx.gcode_path, "a", encoding="utf-8") as f:
>                 f.write(f"\n; processed by Environment Report for {ctx.output_name}\n")
>         except Exception as exc:
>             return orca.ExecutionResult.failure(
>                 orca.PluginResult.RecoverableError,
>                 f"could not append report: {exc}")
>         return orca.ExecutionResult.success("report appended")
>
> Rules enforced when a plugin loads (most in PythonPluginBridge.cpp):
> - The @orca.plugin class must subclass orca.base, and there must be exactly one per file. A second @orca.plugin fails the load.
> - Each class passed to orca.register_capability must subclass a capability base (ultimately orca.PythonPluginBase); otherwise it raises value_error.
> - Every capability must resolve get_name() (checked in the bridge); the loader (PluginLoader.cpp) additionally rejects the plugin if the resulting (type, name) pair is not unique across it.
> - A capability class you never pass to register_capability is invisible to OrcaSlicer, even if it is defined in the file.
> - If the plugin calls orca.request_permissions(...), the user must accept the combined dialog that follows registration; declining it fails the load.
>
> Note: There are no bundled example plugins in the repository. The plugin snippets in this document are illustrative.

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/registry
EXCERPTS:
> | orca.PluginType | enum | PrinterConnection, Pages, Analysis, Importer, Exporter, Visualization, Script, SlicingPipeline, ResourceTexture, Unknown
> | orca.PluginResult | enum | Success, Skipped, RecoverableError, FatalError
> | orca.PythonPluginBase | class | the root capability base; subclasses must implement get_name()
> | orca.base | class | the package base; subclass it and override register_capabilities()
> | orca.plugin | decorator | marks the single package class for the file (exactly one per file)
> | orca.register_capability(cls) | function | register one capability class; call it inside register_capabilities()
> | orca.request_permissions(...) | function | declare filesystem, network, process, and thread permissions up front; call it inside register_capabilities()
>
> Every capability inherits the optional hooks on_load(), on_unload() and on_lifecycle_event(event, ctx) (see Lifecycle Events) from orca.PythonPluginBase, along with these configuration methods:
> | has_config_ui() | Select a custom HTML editor instead of the host JSON editor.
> | get_config_ui() | Return the custom HTML editor page.
> | get_default_config() | Return a Python dict used by Restore defaults; the Python call returns its JSON string.
> | get_config() | Return the effective configuration as a JSON string.
> | get_config_version() | Return the version that last saved the configuration.
> | save_config(config) | Persist a JSON string for this capability; returns False on invalid JSON or write failure.
>
> ## Execution Results
> orca.ExecutionResult.success(message="", data="")
> orca.ExecutionResult.skipped(message="")
> orca.ExecutionResult.failure(status, message, data="")   # status is an orca.PluginResult
> - status - an orca.PluginResult.
> - message - human-readable text; this is what surfaces in error/result dialogs.
> - data - a free-form string whose meaning is defined by the plugin/workflow (not interpreted by the framework).
>
> ## Registration
> @orca.plugin
> class SamplePlugin(orca.base):
>     def register_capabilities(self):
>         orca.register_capability(GCodeBenchmark)
>         orca.register_capability(EnvironmentReport)
>
> ## Permissions
> orca.request_permissions(...) declares, from register_capabilities(), the filesystem, network, process, and thread access the plugin expects. All parameters are optional:
> orca.request_permissions(
>     fs_read=[],           # filesystem paths to read
>     fs_readwrite=[],      # filesystem paths to read/write
>     network_http=[],      # URLs
>     network_socket=[],    # socket addresses, as str() renders them
>     process=[],           # commands / argv
>     threading=False)      # True requests the fixed "thread" target
> - Each list takes the target strings the corresponding audit event reports: paths for the filesystem buckets, a URL for network_http, an address string such as "('example.com', 443)" for network_socket, and a command for process.
> - threading=True requests permission to create one thread; thread creation is granted once per plugin, and the new thread's own work is not audited.
> - OrcaSlicer collects the declarations while register_capabilities() runs and shows one combined Yes/No dialog after it returns and before any capability instance is created. Targets already granted to the plugin are skipped, so declaring them again does not prompt.
> - Declining the dialog aborts the plugin load. An empty string in any list, or calling the function outside plugin discovery, raises ValueError.
> - A declaration pre-approves only the exact target strings listed; any other access still prompts on first use.
>
> ## Capability Names and Types
> get_name() is required; get_type() usually is not. Every capability must implement get_name(). It is pure virtual on the root base, and a missing override fails the load. The typed C++ bases already implement get_type() (for example, ScriptPluginCapability::get_type() returns Script), so a subclass of a typed base does not need to override it.

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/slicing
EXCERPTS:
> The orca.slicing module exposes SlicingPipelineCapabilityBase for plugins that run at points in the slicing pipeline or at the exported-G-code post-processing seam.
> | orca.slicing.SlicingPipelineCapabilityBase | SlicingPipeline | get_name(), execute(self, ctx) -> ExecutionResult | the slicing pipeline and G-code export path
>
> ## Context
> import orca
> class Stamp(orca.slicing.SlicingPipelineCapabilityBase):
>     def get_name(self):
>         return "G-code Stamp"
>     def execute(self, ctx):
>         if ctx.step != orca.slicing.Step.psGCodePostProcess:
>             return orca.ExecutionResult.success()
>         with open(ctx.gcode_path, "a", encoding="utf-8") as gcode:
>             gcode.write("\n; stamped by a plugin\n")
>         return orca.ExecutionResult.success("G-code updated")
>
> During geometry steps, ctx.print and (for object-scoped steps) ctx.object expose the live slicing graph. These references are valid only during execute(ctx). ctx.step identifies the current hook, and ctx.config_value(key) reads a resolved print setting.
> At orca.slicing.Step.psGCodePostProcess, ctx.print and ctx.object are None. The context provides gcode_path, host, and output_name; the plugin edits the working G-code file in place. This step runs after classic post-processing scripts and may run separately for file export and network upload.
> The capability runs on the slicing worker thread. Do not call orca.host.ui.* from it: the GUI may be waiting for slicing to finish, so marshaling a UI call can deadlock.
>
> ## Pipeline steps
> The exposed orca.slicing.Step enum includes geometry steps such as posSlice, posPerimeters, posPrepareInfill, posInfill, posIroning, posContouring, posSupportMaterial, and posSimplifyPath, plus generated-structure steps psWipeTower and psSkirtBrim. The psGCodePostProcess step is the export seam described above.
> Filesystem access is audited: writing to the G-code file at psGCodePostProcess needs no prompt, since its folder is a pre-approved allowed root for the duration of that call. Any other filesystem/network/process action prompts the user with a Yes/No dialog the first time, and the answer is remembered for that plugin.

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/host
EXCERPTS:
> orca.host (bound in src/slic3r/plugin/host/) gives plugins read-only access to the running slicer. It is intended for analysis, reporting, and export plugins; nothing here mutates the model.
> ## Entry Points
> Each entry point raises RuntimeError if called before the GUI/model is ready:
> import orca
> model  = orca.host.model()           # the active Model
> plater = orca.host.plater()          # the Plater
> bundle = orca.host.preset_bundle()   # presets (prints/printers/filaments/...)
> lang   = orca.host.app_language()    # UI language code, e.g. "en_US", "ru_RU"
> store  = orca.host.plugin.storage()  # this plugin's private storage folder
>
> plugin.storage() returns a folder reserved for the calling plugin, creating it if needed, so the plugin can keep data across runs and updates. ... It must be called from a plugin callback (execute(), on_load(), a message handler, ...), not at import time.

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/host_ui
EXCERPTS:
> orca.host.ui lets a plugin show host-owned UI: a native message box, a native progress dialog, a modal HTML dialog, non-modal interactive windows, a panel docked beside the 3D view, and notifications in the 3D view.
> A plugin must never import its own GUI toolkit (PyQt/wxPython/tkinter): a script plugin shares the host's UI thread, so a second toolkit's event loop would clash with wxWidgets, and a gcode / printer-agent plugin can run off the main thread where toolkit calls would crash. These host calls run on the main thread for you and block the calling code until they return.
>
> # Native message box -> returns "ok" | "cancel" | "yes" | "no"
> choice = orca.host.ui.message("Export finished. Open the folder?",
>                               title="My Plugin", buttons="yes_no", icon="question")
> # Modal HTML dialog -> returns the orca.submit() payload (dict), or None if dismissed
> result = orca.host.ui.show_dialog(html="<h2>Hello</h2> ...", title="Report",
>                                   width=820, height=600)
> # Non-modal, persistent, interactive window -> returns a UiWindow handle
> win = orca.host.ui.create_window(html=PAGE, title="Panel",
>                                  on_message=self.on_message, on_close=self.on_close)
> win.post({"type": "data", "rows": [...]})
> message arguments: buttons is "ok"|"ok_cancel"|"yes_no"|"yes_no_cancel"; icon is "info"|"warning"|"error"|"question".
>
> # Docked HTML panel -> returns a UiDockPanel handle
> panel = orca.host.ui.create_dock_panel(html=PAGE, title="My Panel", width=320, height=480,
>                                        on_message=self.on_message, on_close=self.on_close,
>                                        dock="right")
> dock is "left", "right", "bottom" or "float"
>
> create_progress_dialog() ... returns a ProgressDialog handle and also works as a context manager ... The default style is PD_APP_MODAL | PD_AUTO_HIDE; add PD_CAN_ABORT if the user should be able to cancel.
> | progress.update(value, message="") | set the determinate progress value; returns False if closed/cancelled
> | progress.pulse(message="") | advance an indeterminate progress step; returns False if closed/cancelled
> | progress.start_pulse(interval_ms=100, message="") | start timer-driven pulsing on the UI thread
> push_notification() shows a notification in the 3D view
> | orca.postMessage(obj) | deliver obj to the plugin's on_message(obj)
> | orca.onMessage(cb) | cb(data) runs for each win.post(data) (and modal pushes)
> | orca.submit(obj) | (modal) close and return obj from show_dialog
> | orca.close() | close the dialog / window

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/script
EXCERPTS:
> The orca.script module exposes ScriptPluginCapabilityBase for plugins that run from the Plugins dialog.
> | orca.script.ScriptPluginCapabilityBase | Script | get_name(), execute(self) -> ExecutionResult | the Plugins dialog -> Run action
> Lifecycle hooks on_load() / on_unload() are optional and available on every capability (defaults do nothing). So is on_lifecycle_event(event, ctx), which observes application events such as project saves or slicing; see Lifecycle Events.
> ScriptPluginCapabilityBase.execute() runs on the main/UI thread
> class HelloScript(orca.script.ScriptPluginCapabilityBase):
>     def get_name(self):
>         return "Hello Script"
>     def execute(self):
>         return orca.ExecutionResult.success("Hello from a script plugin")

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/lifecycle_events
EXCERPTS:
> Any capability can observe application lifecycle moments (project open/save, slicing, plate and object edits, preset changes, printer and job activity) by overriding on_lifecycle_event(). It is defined on the root orca.PythonPluginBase, so it is available on every capability type, and the default does nothing.
>     def on_lifecycle_event(self, event, ctx):
>         if event == orca.LifecycleEvent.ProjectAfterSave:
>             print("saved", ctx.name)
>         elif event == orca.LifecycleEvent.SlicingJobComplete and ctx.code == orca.LifecycleEvtCode.Error:
>             print("slicing failed:", ctx.msg)
> | Slicing | SliceStarted, SliceGeometryFinished, GCodeExportStarted, GCodeExportFinished, SlicingJobComplete
> | Print / send jobs | PrintJobStarted, PrintJobFinished, SendJobStarted, SendJobFinished
> ## Delivery Rules
> - Every loaded and enabled capability of every plugin receives every event, regardless of capability type. Disabled capabilities are skipped.
> - Events are delivered synchronously on the thread that raised them ... keep handlers short, and never block: the slicer waits for your handler to return.
> - Once a slice is cancelled, dispatch of its slicing and G-code export events stops before the next capability is called.
> - An exception raised by a handler is logged (with the event and payload) and swallowed

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/plugin_audit_hook
EXCERPTS:
> This is an interactive permission system, not a sandbox: a user who clicks Yes has authorized the action, and there is no isolation layer stopping a genuinely malicious plugin from doing damage after that. Today it categorizes and gates filesystem, network, process-spawn, and thread-creation events; native-code loading (ctypes) is not audited, and what a plugin-spawned thread does after it starts is not attributed to the plugin.
>
> enum class AuditEventCategory {
>     None, FsRead, FsReadWrite, FsCreate, FsDelete, Http, Socket, ProcessCreate, Threading,
> };
> | FsRead | glob.glob, glob.glob/2, os.fwalk, os.getxattr, os.listdir, os.listdrives, os.listmounts, os.listvolumes, os.listxattr, os.scandir, os.walk, pathlib.Path.glob, pathlib.Path.rglob
> | FsReadWrite | os.chflags, os.chmod, os.chown, os.removexattr, os.rename, os.setxattr, os.truncate, os.utime, shutil.chown, shutil.copymode, shutil.copystat, shutil.copyfile, shutil.copytree, shutil.make_archive, shutil.move, shutil.unpack_archive
> | FsCreate | os.link, os.mkdir, os.symlink, tempfile.mkdtemp, tempfile.mkstemp, _winapi.CreateJunction
> | FsDelete | os.remove, os.rmdir, shutil.rmtree
> | Http | http.client.connect, http.client.send, urllib.Request
> | Socket | socket.__new__, socket.bind, socket.connect, socket.getaddrinfo, socket.gethostbyaddr, socket.gethostbyname, socket.gethostname, socket.getnameinfo, socket.getservbyname, socket.getservbyport, socket.sendmsg, socket.sendto
> | ProcessCreate | os.fork, os.forkpty, os.posix_spawn, os.spawn, os.system, os.startfile, os.startfile/2, pty.spawn, subprocess.Popen, _winapi.CreateProcess, _posixsubprocess.fork_exec
> | Threading | _thread.start_new_thread (thread creation; threading.Thread reaches it through this call, but the new thread's own work is not audited)
>
> ### Allowed Roots and Denied Paths
> | Root | Access | Covers
> | data_dir() (global) | read+write | each plugin's storage folder (data_dir()/orca_plugins), the installed/system profile cache (data_dir()/system), and the rest of data_dir()
> | resources_dir() (global) | read-only | the app's bundled, shared assets ... never write-eligible
> | current G-code file's parent directory (scoped, SlicingPipelinePluginCapabilityTrampoline::execute()) | read+write | only while a psGCodePostProcess call is on the stack, and only for that call
> Denied filenames: default_denied_filenames() (the app config, both extensions and app keys, plus the cloud refresh token). Denied keywords: default_denied_path_keywords() = {"secret", "cert", "conf"}
> - On No: report_denied records an AuditViolation, raises PermissionError in the calling interpreter, and the hook returns -1 — CPython treats a nonzero return as "block this operation," so the audited call never completes.
> FsCreate/FsDelete always prompt, with nothing remembered across calls
> "permissions": { "fs_read": [...], "fs_readwrite": [], "network_http": ["http://example.com"], "network_socket": ["('example.com', 80)"], "process": ["/usr/bin/python3"], "threading": ["thread"], "events": ["Socket:socket.__new__"] }
> - No prompt appears at all. Check whether the target was already granted (persisted in the plugin's .install_state.json sidecar, either reactively or through orca.request_permissions(...)) or covered by the ancestor cascade — both allow silently by design, not a bug.
> - First use is denied while a prompt is still open. Off the main thread the prompt is posted asynchronously and the current event is denied (fail closed).

SOURCES:
- https://www.orcaslicer.com/wiki/plugins/plugins_types
EXCERPTS:
> ## Slicing Pipeline
> Mode: Advanced.
> Variable: slicing_pipeline_plugin.
> Type: Text list.
> CLI Example: --slicing-pipeline-plugin=value.
> Slicing-pipeline plugins run at selected points in the slicing workflow. They can inspect or modify the live slicing graph, or edit the exported G-code at the post-processing step. This capability is experimental and intended for plugin developers and testers.
> The psGCodePostProcess step runs after the classic post-processing scripts and receives the working G-code path; geometry steps receive the active slicing context instead.
> Slicing-pipeline plugins can change generated geometry or G-code. Review and test plugins from sources you trust before using them for a print.
>
> ## Plugin Configuration
> Select a plugin, open the Config tab, and select one of its capabilities. Edit the JSON configuration and click Save. Restore defaults removes the saved configuration for that capability and uses the plugin's default configuration.
> When a preset uses a plugin capability, its configuration can also be overridden for that preset. The override is stored with the preset when you save it; otherwise the capability uses its global configuration.
>
> ## Printer Connection
> Printer connection plugins add printer communication features. The Printer Agent workflow is still WIP.
> For printers that are not Bambu Lab printers, OrcaSlicer only sends print jobs through a printer connection plugin when Preferences > Developer > Experimental Features > Use printer agents instead of print hosts is enabled. It is off by default, so the classic print host upload is used.

SOURCES:
- https://github.com/OrcaSlicer/OrcaSlicer/releases/tag/v2.5.0-alpha
EXCERPTS:
> # 🧩 Plugins
> OrcaSlicer 2.5.0 introduces **Python plugins**, a supported way to add your own features to the slicer without maintaining a fork. A plugin can add one-click scripts, step into slicing to reshape layers or rewrite the G-code, add its own tab or docked panel, or react to events like a finished print. Open **Plugins** from the main menu to install a plugin from a file or from Orca Cloud. A plugin must ask your permission before it reaches outside OrcaSlicer's data folder, goes online or starts other programs. The plugin system is new and its API may still change, so feedback from users and plugin authors is very welcome.
>
> * **Python plugins** ... A plugin is a single `.py` file or a `.whl` package, and the Python packages it depends on are installed automatically (on Windows ARM64 too). ... One plugin can provide several capabilities: **Script** actions run from the Plugins window or the Speed Dial, **Slicing Pipeline** steps run while you slice, **Pages** add their own tab to the main window, and **Resource Texture** packs add height-map textures to the Texture Displacement picker.
>
> * **Slicing-pipeline plugins** by @SoftFever in #14721
>     A plugin can take part in slicing itself. Pick one or more under **Process > Others > Slicing Pipeline Plugin** (Advanced mode) to read and edit the sliced layers, with the walls, infill, preview and G-code following their changes, or to post-process the exported G-code. Plugin errors show up as ordinary slicing errors rather than crashing OrcaSlicer. Sample plugins twist, taper or wobble any model as it slices, and apply fuzzy skin to the sliced outline so the infill follows the fuzzy wall too. This is experimental and aimed at plugin developers and testers.
>
> * **Plugin settings, globally or per preset** by @peachismomo and @SoftFever in #14746, #14944 and #14862
>     The **Config** tab in the Plugins window holds each capability's settings, in a built-in JSON editor or the plugin's own settings page, and **Restore defaults** puts the defaults back. The process, filament and printer settings each have a **Plugin Configuration** group (Advanced mode) whose **Configure** button overrides those settings for that preset only. ... Changes to a slicing plugin's settings take effect on the next slice, settings survive plugin updates and reinstalls, and leftover overrides are cleaned up when a preset stops using a plugin.
>
> * **Permission prompts for plugins** by @SoftFever, @peachismomo and @HanifKoh in #14821, #14989, #16243, #16248, #16254, #16255 and #16253
>     Plugins can't read OrcaSlicer's own config file or your Orca Cloud login token, and folders named like `secrets`, `certs` or `config` and `.conf`/`.ini` files are blocked the same way. When a plugin tries to work with files outside OrcaSlicer's data folder, connect to the network, launch another program (or replace OrcaSlicer with one) or start a background thread, a prompt names the plugin and what it wants, and your answer is remembered. A plugin can list the files it needs up front, so you're asked once when it loads.
>
> * **More for plugin authors: events, notifications and app info** ... Plugins can react to **lifecycle events**: projects opened, saved or closed; slicing and G-code export starting and finishing; objects and plates added, moved, renamed or deleted; presets selected or saved; printers discovered or connected; and uploads and print jobs starting and finishing.

SOURCES:
- https://www.orcaslicer.com/wiki/developer_reference/plugin_development/api_reference/printer_agent
EXCERPTS:
> The orca.printer_agent module exposes PrinterAgentBase and its data types. A printer agent is the layer OrcaSlicer talks to for everything on the Device side: discovering printers, connecting to one, sending commands, pushing status back, and sending or starting print jobs. OrcaSlicer ships built-in agents (Bambu Lab, Moonraker, Qidi, Snapmaker, CrealityPrint, Orca).
> | orca.printer_agent.PrinterAgentBase | PrinterConnection | get_name(), get_agent_info(), plus the core agent methods listed under Methods | the network / printer-agent layer (NetworkAgent) once the agent is selected
> - The IDs orca, bbl, qidi, snapmaker, crealityprint and moonraker belong to the built-in agents. ... An empty value means the default: bbl for Bambu Lab printers and orca for everything else.
> | start_local_print(self, params, update_fn, cancel_fn) | int | Print over LAN | -1
> | start_print(self, params, update_fn, cancel_fn, wait_fn) | int | cloud print | -1
> | start_send_gcode_to_sdcard(self, params, update_fn, cancel_fn, wait_fn) | int | Send (upload without printing). ... | -1
> | start_sdcard_print(self, params, update_fn, cancel_fn) | int | print a file already on the printer's storage | -1

MISSING:
- "Repeat the print N times" / re-run or re-queue a finished job N times: no plugin capability, hook, or API for this is described on any page read (plugin_system, plugin_development, api_reference/{registry,slicing,host,host_ui,script,lifecycle_events,pages,printer_agent,resource_texture}, plugin_audit_hook, plugins/{plugins_types,plugins_getting_started,plugins_management,plugins_local}) nor in the v2.5.0-alpha notes. The slicing-pipeline/printer-agent docs mention starting print/send *jobs* only via lifecycle events (PrintJobStarted/Finished, SendJobStarted/Finished) and the PrinterAgentBase "start_*" methods, but say nothing about looping a print N times.
- An API to read G-code *content* after slicing (parsing/scanning the sliced file, or the machine's end G-code): the docs only expose the working file path ctx.gcode_path at psGCodePostProcess and tell the plugin to open/edit "the working G-code file in place" (api_reference/slicing, plugin_development). No line/text read API, no accessor for the printer's start/end G-code, was found; how to "replace the end G-code" is not specified anywhere I looked.
- Bambu Lab A1-specific plugin guidance: the A1 appears only incidentally in the v2.5.0-alpha notes (arranging behaviour for i3-style printers such as the Bambu Lab A1; a JAYO filament profile for the A1), not in any plugin/dev page. No A1 printer-agent or end-G-code documentation found.
- A hook attached specifically "after slicing a Bambu Lab A1 job" (printer-model-filtered callback): not documented; hooks are type-based (slicing-pipeline execute(ctx), script execute(), on_lifecycle_event, on_load/on_unload), not per-printer-model.
- Whether slicing-pipeline post-process runs separately for file export vs. network upload is stated ("may run separately for file export and network upload") but no Bambu/printer-agent upload path for the A1 is documented in the plugin pages.
- No bundled/working example plugin source in the repo is available to quote: plugin_development states "There are no bundled example plugins in the repository. The plugin snippets in this document are illustrative."