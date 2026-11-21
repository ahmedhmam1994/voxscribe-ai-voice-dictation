import 'package:flutter/foundation.dart';

/// One spoken note in the inbox: saved, never typed.
@immutable
class Note {
  const Note({required this.id, required this.text, required this.createdAt});

  final int id;
  final String text;
  final DateTime createdAt;
}
