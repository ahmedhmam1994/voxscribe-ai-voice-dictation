package com.voxscribe.android

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

/** Hosts the Flutter UI. The floating button, typing service and engine stay native. */
class MainActivity : FlutterActivity() {
    private val wordListFiles = WordListFilesChannel(this)
    private val fileImport = ImportChannel(this)

    override fun onCreate(savedInstanceState: android.os.Bundle?) {
        super.onCreate(savedInstanceState)
        rememberShared(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        rememberShared(intent)
    }

    /** A voice note or recording shared from another app waits here until the screen asks for it. */
    private fun rememberShared(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        @Suppress("DEPRECATION")
        val uri = intent.getParcelableExtra<android.net.Uri>(Intent.EXTRA_STREAM) ?: return
        ImportChannel.sharedUri = uri
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger
        SetupChannel(this).register(messenger)
        EngineChannel(this).register(messenger)
        FastModelChannel(this).register(messenger)
        HistoryChannel(this).register(messenger)
        SettingsChannel(this).register(messenger)
        ProChannel(this).register(messenger)
        TextToolsChannel(this).register(messenger)
        TermPacksChannel(this).register(messenger)
        ReadAloudChannel(this).register(messenger)
        NetworkLogChannel(this).register(messenger)
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
