plugins {
    id("com.android.application")
}

android {
    namespace = "com.hinawihako.toefldaily"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.hinawihako.toefldaily"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // 只依赖系统 WebView，不需要额外库
}
