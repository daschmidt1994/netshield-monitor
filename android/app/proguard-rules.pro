# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers @kotlinx.serialization.Serializable class ** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class io.github.daschmidt1994.netshield.data.**$$serializer { *; }
# Retrofit interfaces
-keep,allowobfuscation interface io.github.daschmidt1994.netshield.data.NetShieldService
-keepattributes Signature, Exceptions
