import 'dart:io';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// حفظ الصور بشكل دائم داخل مجلد التطبيق (لا تُحذف بمسح الكاش)
class ImageStore {
  static Future<Directory> _dir() async {
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory(p.join(base.path, 'aph_images'));
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  /// اختيار صورة (كاميرا/معرض) ونسخها نسخة دائمة — يرجع المسار الدائم أو null
  static Future<String?> pickAndPersist(ImageSource source) async {
    final picked = await ImagePicker()
        .pickImage(source: source, maxWidth: 900, imageQuality: 78);
    if (picked == null) return null;
    final dir = await _dir();
    final ext = p.extension(picked.path).isEmpty ? '.jpg' : p.extension(picked.path);
    final dest = p.join(
        dir.path, 'img_${DateTime.now().millisecondsSinceEpoch}$ext');
    await File(picked.path).copy(dest);
    return dest;
  }

  static bool isRemote(String path) =>
      path.startsWith('http://') || path.startsWith('https://');
}
