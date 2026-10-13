/// APH AI Assistant (§41–§43) — RAG over the verified knowledge base.
/// Every answer carries citations for retrieved sources and the medical
/// disclaimer. Unavailable information is never fabricated.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';

class AiAssistantScreen extends StatefulWidget {
  const AiAssistantScreen({super.key});

  @override
  State<AiAssistantScreen> createState() => _AiAssistantScreenState();
}

class _ChatMessage {
  _ChatMessage({required this.role, required this.text, this.citations = const [], this.grounded = true});
  final String role; // user | assistant
  final String text;
  final List<dynamic> citations;
  final bool grounded;
}

class _AiAssistantScreenState extends State<AiAssistantScreen> {
  final _controller = TextEditingController();
  final _messages = <_ChatMessage>[];
  final _scroll = ScrollController();
  String? _conversationId;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final t = AppLocalizations.of(context);
      setState(() {
        _messages.add(_ChatMessage(role: 'assistant', text: t.tr('aiDisclaimer'), grounded: true));
      });
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final question = _controller.text.trim();
    if (question.isEmpty || _busy) return;
    final t = AppLocalizations.of(context);
    final app = context.read<AppState>();
    setState(() {
      _messages.add(_ChatMessage(role: 'user', text: question));
      _busy = true;
      _controller.clear();
    });
    _scrollDown();

    try {
      final result = await app.repository.askAi(
        question,
        language: app.isArabic ? 'ar' : 'en',
        conversationId: _conversationId,
      );
      _conversationId = (result['conversation_id'] ?? _conversationId) as String?;
      setState(() {
        _messages.add(_ChatMessage(
          role: 'assistant',
          text: (result['answer'] ?? '').toString(),
          citations: (result['citations'] as List?) ?? const [],
          grounded: result['grounded'] == true,
        ));
        _busy = false;
      });
    } catch (_) {
      setState(() {
        _messages.add(_ChatMessage(role: 'assistant', text: t.tr('networkError'), grounded: false));
        _busy = false;
      });
    }
    _scrollDown();
  }

  void _scrollDown() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('aiAssistant')),
      body: Column(children: [
        Container(
          width: double.infinity,
          color: AphColors.amber.withValues(alpha: 0.1),
          padding: const EdgeInsets.symmetric(horizontal: AphSpacing.md, vertical: 8),
          child: Text(
            t.tr('aiDisclaimer'),
            style: const TextStyle(fontSize: 10.5, height: 1.4, color: AphColors.amber),
          ),
        ),
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(AphSpacing.md),
            itemCount: _messages.length + (_busy ? 1 : 0),
            itemBuilder: (context, i) {
              if (i == _messages.length) {
                return const Padding(
                  padding: EdgeInsets.all(12),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              return _buildMessage(_messages[i], t);
            },
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AphSpacing.md),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: InputDecoration(hintText: t.tr('aiHint')),
                ),
              ),
              const SizedBox(width: 10),
              FilledButton(
                onPressed: _send,
                child: const Icon(Icons.send),
              ),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _buildMessage(_ChatMessage m, AppLocalizations t) {
    final isUser = m.role == 'user';
    return Align(
      alignment: isUser ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isUser ? AphColors.cyan : AphColors.surface,
          borderRadius: BorderRadius.circular(AphSpacing.radius),
          border: isUser ? null : Border.all(color: AphColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(m.text,
                style: TextStyle(
                  color: isUser ? Colors.white : AphColors.textPrimary,
                  height: 1.5,
                  fontSize: 13.5,
                )),
            if (!isUser && !m.grounded) ...[
              const SizedBox(height: 8),
              Text(t.tr('aiUnavailable'),
                  style: const TextStyle(fontSize: 11, color: AphColors.amber, fontStyle: FontStyle.italic)),
            ],
            if (m.citations.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Divider(height: 1),
              const SizedBox(height: 8),
              Text(t.tr('sources'),
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AphColors.cyan)),
              const SizedBox(height: 4),
              ...m.citations.map((c) => Padding(
                    padding: const EdgeInsets.only(bottom: 3),
                    child: Text(
                      '• ${(c['source_name'] ?? '')} — ${(c['section'] ?? '')}',
                      style: const TextStyle(fontSize: 11, color: AphColors.textSecondary),
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}
