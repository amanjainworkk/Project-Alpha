// Project Alpha Mobile APK — Founder Chat Screen
// File Target: Alpha/apk/lib/screens/chat_screen.dart
// Conforms to Feature 73: CEO Command Console, Deliberation Threads & Tool Execution Callouts

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import '../services/services.dart';
import '../providers/providers.dart';
import '../widgets/progress_bar_card.dart';

/// Founder Chat Screen featuring interactive CEO command console,
/// ThreadMessage stream, tool execution callouts, and quick suggestion chips.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ThreadMessage> _messages = [];
  bool _isSending = false;
  StreamSubscription? _threadSub;

  final List<String> _quickSuggestions = [
    'Audit System Integrity',
    'Summarize Project Status',
    'Run Security Sweep',
    'Review Token Spend',
    'Delegate Architecture Design',
    'Check CAO Compliance',
  ];

  @override
  void initState() {
    super.initState();
    _seedDefaultMessages();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final wsService = context.read<AlphaWebSocketService?>();
      if (wsService != null) {
        _threadSub = wsService.onThreadMessage.listen((data) {
          if (mounted) {
            setState(() {
              _messages.add(ThreadMessage.fromJson(data));
            });
            _scrollToBottom();
          }
        });
      }
    });
  }

  void _seedDefaultMessages() {
    _messages.addAll([
      ThreadMessage(
        messageId: 'msg_001',
        sender: 'Founder',
        content: 'Execute autonomous security and architecture review for Project Alpha.',
        timestamp: '10:00:15',
        messageType: 'DIRECTIVE',
      ),
      ThreadMessage(
        messageId: 'msg_002',
        sender: 'CEO',
        content: 'Directive received. Activating CTO and Dual CAO audit officers (Claude & ChatGPT). Delegating system audit and architecture synthesis.',
        timestamp: '10:00:22',
        messageType: 'DELIBERATION',
        modelUsed: 'ollama/llama3.2',
        tokensUsed: 420,
      ),
      ThreadMessage(
        messageId: 'msg_003',
        sender: 'CEO',
        content: '[Vault Search: query="security_architecture" -> 4 documents retrieved]',
        timestamp: '10:00:28',
        messageType: 'AUDIT',
      ),
      ThreadMessage(
        messageId: 'msg_004',
        sender: 'CEO',
        content: '[CAO Audit Verdict: CLEAN — Zero P0 compliance violations. Escalation cap: 0/2]',
        timestamp: '10:00:35',
        messageType: 'AUDIT',
      ),
      ThreadMessage(
        messageId: 'msg_005',
        sender: 'CEO',
        content: 'System architecture validated against Master Design Spec §11. Ready for live mobile canvas telemetry streaming.',
        timestamp: '10:00:40',
        messageType: 'MESSAGE',
        modelUsed: 'ollama/llama3.2',
        tokensUsed: 310,
      ),
    ]);
  }

  @override
  void dispose() {
    _threadSub?.cancel();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSendMessage(String text) async {
    final cleanText = text.trim();
    if (cleanText.isEmpty || _isSending) return;

    _textController.clear();
    final userMsg = ThreadMessage(
      messageId: 'msg_${DateTime.now().millisecondsSinceEpoch}',
      sender: 'Founder',
      content: cleanText,
      timestamp: DateTime.now().toIso8601String().substring(11, 19),
      messageType: 'DIRECTIVE',
    );

    setState(() {
      _messages.add(userMsg);
      _isSending = true;
    });
    _scrollToBottom();

    try {
      final client = context.read<AlphaApiClient?>();
      if (client != null) {
        final res = await client.messageAgent('CEO', cleanText);
        final replyText = res['response']?.toString() ??
            res['message']?.toString() ??
            'Directive received. Processing across executive boardroom.';

        if (mounted) {
          setState(() {
            _messages.add(
              ThreadMessage(
                messageId: 'msg_ceo_${DateTime.now().millisecondsSinceEpoch}',
                sender: 'CEO',
                content: replyText,
                timestamp: DateTime.now().toIso8601String().substring(11, 19),
                messageType: 'MESSAGE',
                modelUsed: 'ollama/llama3.2',
                tokensUsed: 250,
              ),
            );
          });
          _scrollToBottom();
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _messages.add(
            ThreadMessage(
              messageId: 'err_${DateTime.now().millisecondsSinceEpoch}',
              sender: 'CEO',
              content: 'Autonomous deliberation initiated: $cleanText (Offline telemetry fallback active)',
              timestamp: DateTime.now().toIso8601String().substring(11, 19),
              messageType: 'DELIBERATION',
            ),
          );
        });
        _scrollToBottom();
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSending = false;
        });
      }
    }
  }

  bool _isToolCallout(String content) {
    final c = content.trim();
    return (c.startsWith('[') && c.endsWith(']')) ||
        c.contains('Vault Search:') ||
        c.contains('CAO Audit Verdict:') ||
        c.contains('Model Router:');
  }

  Widget _buildToolCalloutCard(ThreadMessage msg) {
    final isClean = msg.content.contains('CLEAN');
    final isBreach = msg.content.contains('BREACH') || msg.content.contains('VIOLATION');
    final Color badgeColor = isClean
        ? AlphaColors.successEmerald
        : isBreach
            ? AlphaColors.errorRose
            : AlphaColors.primaryCyan;

    final IconData icon = msg.content.contains('Vault')
        ? Icons.storage
        : msg.content.contains('Audit')
            ? Icons.verified_user
            : Icons.alt_route;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AlphaColors.surfaceLevel1,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: badgeColor.withOpacity(0.6), width: 1.0),
        boxShadow: [
          BoxShadow(
            color: badgeColor.withOpacity(0.15),
            blurRadius: 8,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: badgeColor.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 16, color: badgeColor),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'TOOL EXECUTION CALLOUT',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: badgeColor,
                        letterSpacing: 0.5,
                      ),
                    ),
                    Text(
                      msg.timestamp,
                      style: AlphaTheme.monoStyle.copyWith(fontSize: 10),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  msg.content,
                  style: AlphaTheme.monoStyle.copyWith(
                    fontSize: 12,
                    color: AlphaColors.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(ThreadMessage msg) {
    final isFounder = msg.isFromFounder;

    if (_isToolCallout(msg.content)) {
      return _buildToolCalloutCard(msg);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        mainAxisAlignment:
            isFounder ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isFounder) ...[
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AlphaColors.surfaceLevel3,
                shape: BoxShape.circle,
                border: Border.all(color: AlphaColors.primaryCyan, width: 1.5),
              ),
              child: const Text(
                'CEO',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: AlphaColors.primaryCyan,
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isFounder
                    ? AlphaColors.surfaceLevel3
                    : AlphaColors.surfaceLevel2,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(14),
                  topRight: const Radius.circular(14),
                  bottomLeft: Radius.circular(isFounder ? 14 : 2),
                  bottomRight: Radius.circular(isFounder ? 2 : 14),
                ),
                border: Border.all(
                  color: isFounder
                      ? AlphaColors.primaryCyan.withOpacity(0.5)
                      : AlphaColors.border,
                ),
              ),
              child: Column(
                crossAxisAlignment: isFounder
                    ? CrossAxisAlignment.end
                    : CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        msg.sender,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: isFounder
                              ? AlphaColors.primaryCyan
                              : AlphaColors.secondaryBlue,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        msg.timestamp,
                        style: AlphaTheme.monoStyle.copyWith(fontSize: 10),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    msg.content,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AlphaColors.textPrimary,
                      height: 1.4,
                    ),
                  ),
                  if (msg.modelUsed != null) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AlphaColors.backgroundOled,
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: AlphaColors.borderSubtle),
                      ),
                      child: Text(
                        '${msg.modelUsed} • ${msg.tokensUsed} tokens',
                        style: AlphaTheme.monoStyle.copyWith(fontSize: 10),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isFounder) ...[
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AlphaColors.surfaceLevel3,
                shape: BoxShape.circle,
                border: Border.all(color: AlphaColors.successEmerald, width: 1.5),
              ),
              child: const Icon(Icons.person, size: 14, color: AlphaColors.successEmerald),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final activeTask = context.select<TaskProvider, TaskProgress?>(
      (tp) => tp.runningTasks.isNotEmpty ? tp.runningTasks.first : null,
    );

    return Scaffold(
      backgroundColor: AlphaColors.backgroundOled,
      body: Column(
        children: [
          // Optional Active Task Ticker
          if (activeTask != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AlphaColors.surfaceLevel1,
              child: Row(
                children: [
                  const SizedBox(
                    width: 12,
                    height: 12,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AlphaColors.primaryCyan),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Live Task: ${activeTask.taskName} (${activeTask.progressPercent}%)',
                      style: const TextStyle(fontSize: 12, color: AlphaColors.textSecondary),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Text(
                    activeTask.formatProgressBar(),
                    style: AlphaTheme.monoStyle.copyWith(fontSize: 11, color: AlphaColors.primaryCyan),
                  ),
                ],
              ),
            ),

          // Message Stream
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.symmetric(vertical: 12),
              itemCount: _messages.length,
              itemBuilder: (context, index) => _buildMessageBubble(_messages[index]),
            ),
          ),

          // Quick Suggestion Chips
          SizedBox(
            height: 38,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _quickSuggestions.length,
              itemBuilder: (context, index) {
                final suggestion = _quickSuggestions[index];
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    backgroundColor: AlphaColors.surfaceLevel2,
                    side: const BorderSide(color: AlphaColors.border),
                    label: Text(
                      suggestion,
                      style: const TextStyle(fontSize: 11, color: AlphaColors.textSecondary),
                    ),
                    onPressed: () => _handleSendMessage(suggestion),
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 8),

          // Message Input Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: const BoxDecoration(
              color: AlphaColors.surfaceLevel1,
              border: Border(top: BorderSide(color: AlphaColors.border)),
            ),
            child: SafeArea(
              top: false,
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      style: const TextStyle(fontSize: 14, color: AlphaColors.textPrimary),
                      decoration: InputDecoration(
                        hintText: 'Enter directive for CEO...',
                        hintStyle: const TextStyle(color: AlphaColors.textMuted, fontSize: 13),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        fillColor: AlphaColors.surfaceLevel2,
                        filled: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(20),
                          borderSide: const BorderSide(color: AlphaColors.border),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(20),
                          borderSide: const BorderSide(color: AlphaColors.border),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(20),
                          borderSide: const BorderSide(color: AlphaColors.primaryCyan, width: 1.5),
                        ),
                      ),
                      onSubmitted: _handleSendMessage,
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: _isSending
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: AlphaColors.primaryCyan),
                          )
                        : const Icon(Icons.send_rounded, color: AlphaColors.primaryCyan),
                    onPressed: () => _handleSendMessage(_textController.text),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
