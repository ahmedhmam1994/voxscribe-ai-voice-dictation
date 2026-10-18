package com.voxscribe.android

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

/** Hosts the Flutter UI. The floating button, typing service and engine stay native. */
class MainActivity : FlutterActivity() {
    private val wordListFiles = WordListFilesChannel(this)
    private val fileImport = ImportChannel(this)

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger
        SetupChannel(this).register(messenger)
        EngineChannel(this).register(messenger)
        HistoryChannel(this).register(messenger)
        SettingsChannel(this).register(messenger)
        ProChannel(this).register(messenger)
        TextToolsChannel(this).register(messenger)
        ReleaseChannel(this).register(messenger)
        wordListFiles.register(messenger)
        fileImport.register(messenger)
        Telemetry.sendIfDue(this)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (wordListFiles.onActivityResult(requestCode, resultCode, data)) return
        if (fileImport.onActivityResult(requestCode, resultCode, data)) return
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
    }
}
