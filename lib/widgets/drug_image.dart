import 'dart:io';
import 'package:flutter/material.dart';
import '../services/image_store.dart';

/// صورة دواء/منتج: ملف محلي دائم أو رابط إنترنت، مع بديل أنيق عند الغياب
class DrugImage extends StatelessWidget {
  final String path;
  final double size;
  const DrugImage({super.key, required this.path, this.size = 58});

  @override
  Widget build(BuildContext context) {
    final placeholder = Container(
      width: size, height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(15),
        gradient: const LinearGradient(
            colors: [Color(0xFF14532D), Color(0xFF0F766E)]),
      ),
      child: Icon(Icons.medication, color: Colors.white, size: size * 0.5),
    );
    if (path.isEmpty) return placeholder;
    if (ImageStore.isRemote(path)) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(15),
        child: Image.network(path, width: size, height: size,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => placeholder),
      );
    }
    final f = File(path);
    return ClipRRect(
      borderRadius: BorderRadius.circular(15),
      child: Image.file(f, width: size, height: size, fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => placeholder),
    );
  }
}
