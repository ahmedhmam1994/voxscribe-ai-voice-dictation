import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android Gradle Plugin.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing reads keystore.properties (untracked), so a fresh checkout
// without it still builds debug and unsigned-release variants.
val keystoreProperties = Properties().apply {
    val file = rootProject.file("keystore.properties")
    if (file.exists()) file.inputStream().use(::load)
}
val hasReleaseSigning = keystoreProperties.containsKey("storeFile")

android {
    namespace = "com.voxscribe.android"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Keep the original id: existing installs update in place.
        applicationId = "com.voxscribe.android"
        minSdk = 26
        // Held at 34 until the foreground-service and overlay behavior has been
        // re-tested against newer targets.
        targetSdk = 34
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = rootProject.file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // No shrinking: the native speech library is called through JNI and
            // must not be stripped.
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.getByName(if (hasReleaseSigning) "release" else "debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    // Material 3 for the native keyboard UI (classic Views, not Compose).
    implementation("com.google.android.material:material:1.12.0")
    // Offline recognizer. A prebuilt AAR from k2-fsa/sherpa-onnx, downloaded by
    // hand into libs/ (see libs/README.md), because it is not on Maven Central.
    implementation(files("libs/sherpa-onnx-1.13.6.aar"))

    // Ed25519 for checking Pro license keys. Not in the JDK until Android 13.
    implementation("net.i2p.crypto:eddsa:0.3.0")

    testImplementation("junit:junit:4.13.2")
}

flutter {
    source = "../.."
}
