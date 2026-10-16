import 'package:flutter/services.dart';
import 'package:voxscribe_app/features/texttools/domain/word_list_files.dart';

/// Talks to `WordListFilesChannel.kt`, which opens Android's file picker.
class MethodChannelWordListFiles implements WordListFiles {
  static const _channel = MethodChannel('com.voxscribe.android/wordlistfiles');

  @override
  Future<String?> save(String fileName, String text) async {
    try {
      return await _channel.invokeMethod<String>('saveFile', {
        'fileName': fileName,
        'text': text,
      });
    } on PlatformException catch (e) {
      throw WordListFileException(e.message ?? 'Could not save the file.');
    } on MissingPluginException {
      throw const WordListFileException('Could not open the file picker.');
    }
  }

  @override
  Future<String?> open() async {
    try {
      return await _channel.invokeMethod<String>('openFile');
    } on PlatformException catch (e) {
      throw WordListFileException(e.message ?? 'Could not read the file.');
    } on MissingPluginException {
      throw const WordListFileException('Could not open the file picker.');
    }
  }
}
