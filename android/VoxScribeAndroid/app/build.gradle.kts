import java.util.Properties

plugins {
    id("com.android.application")
}

// Release signing reads from keystore.properties (untracked -- see
// .gitignore), so a fresh checkout without that file can still build a
// debug APK / unsigned release build. Play Store uploads need this filled
// in with a real keystore's path/passwords/alias.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("keystore.properties")
val hasReleaseSigning = keystorePropertiesFile.exists()
if (hasReleaseSigning) {
    keystoreProperties.load(keystorePropertiesFile.inputStream())
}

android {
    namespace = "com.voxscribe.android"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.voxscribe.android"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = rootProject.file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasReleaseSigning) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    // Material Design 3 components (MaterialButton, MD3 color/shape/type
    // tokens) for the keyboard UI -- classic View system, not Compose.
    // Compose inside an InputMethodService needs a hand-rolled
    // LifecycleOwner/ViewModelStoreOwner to attach a ComposeView, which is a
    // real, well-known rough edge even in verified builds; not worth
    // stacking on top of Milestone 2's already-unverified code.
    implementation("com.google.android.material:material:1.12.0")

    // sherpa-onnx's offline (bundled-model) speech recognizer -- see
    // Milestone 2 in README-ANDROID.md for where to get this file. It's a
    // real prebuilt AAR published by the k2-fsa/sherpa-onnx project itself
    // (not a Maven dependency -- they don't publish to Maven Central), so it
    // has to be downloaded once and dropped into app/libs/ by hand.
    implementation(files("libs/sherpa-onnx-1.13.6.aar"))
}
