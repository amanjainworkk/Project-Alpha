// Alpha Mobile — ThreadMessage Data Model
// Conforms to PROJECT.md Feature 67, 73 (CEO Command Center Chat & Deliberation Threads)

class ThreadMessage {
  final String messageId;
  final String sender;
  final String content;
  final String timestamp;
  final String messageType; // 'MESSAGE', 'DIRECTIVE', 'DELIBERATION', 'AUDIT'
  final String? threadId;
  final String? projectId;
  final List<String> toAgents;
  final String? modelUsed;
  final int tokensUsed;
  final String status;

  ThreadMessage({
    required this.messageId,
    required this.sender,
    required this.content,
    required this.timestamp,
    required this.messageType,
    this.threadId,
    this.projectId,
    this.toAgents = const [],
    this.modelUsed,
    this.tokensUsed = 0,
    this.status = 'sent',
  });

  factory ThreadMessage.fromJson(Map<String, dynamic> json) {
    return ThreadMessage(
      messageId: (json['message_id'] ?? json['messageId'] ?? json['id'] ?? '').toString(),
      sender: (json['sender'] ?? json['from_agent'] ?? json['from'] ?? '').toString(),
      content: (json['content'] ?? '').toString(),
      timestamp: json['timestamp']?.toString() ?? '',
      messageType: (json['message_type'] ?? json['messageType'] ?? json['type'] ?? 'MESSAGE').toString(),
      threadId: json['thread_id']?.toString() ?? json['threadId']?.toString(),
      projectId: json['project_id']?.toString() ?? json['projectId']?.toString(),
      toAgents: (json['to_agents'] ?? json['toAgents'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      modelUsed: json['model_used']?.toString() ?? json['modelUsed']?.toString(),
      tokensUsed: (json['tokens_used'] ?? json['tokensUsed'] as num?)?.toInt() ?? 0,
      status: (json['status'] ?? 'sent').toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'message_id': messageId,
        'messageId': messageId,
        'sender': sender,
        'from': sender,
        'content': content,
        'timestamp': timestamp,
        'message_type': messageType,
        'messageType': messageType,
        'type': messageType,
        if (threadId != null) 'thread_id': threadId,
        if (projectId != null) 'project_id': projectId,
        'to_agents': toAgents,
        if (modelUsed != null) 'model_used': modelUsed,
        'tokens_used': tokensUsed,
        'status': status,
      };

  bool get isDeliberation => messageType == 'DELIBERATION';
  bool get isDirective => messageType == 'DIRECTIVE';
  bool get isAudit => messageType == 'AUDIT';
  bool get isFromFounder =>
      sender.toLowerCase() == 'founder' || sender.toLowerCase() == 'user';

  ThreadMessage copyWith({
    String? messageId,
    String? sender,
    String? content,
    String? timestamp,
    String? messageType,
    String? threadId,
    String? projectId,
    List<String>? toAgents,
    String? modelUsed,
    int? tokensUsed,
    String? status,
  }) {
    return ThreadMessage(
      messageId: messageId ?? this.messageId,
      sender: sender ?? this.sender,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      messageType: messageType ?? this.messageType,
      threadId: threadId ?? this.threadId,
      projectId: projectId ?? this.projectId,
      toAgents: toAgents ?? this.toAgents,
      modelUsed: modelUsed ?? this.modelUsed,
      tokensUsed: tokensUsed ?? this.tokensUsed,
      status: status ?? this.status,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ThreadMessage &&
          runtimeType == other.runtimeType &&
          messageId == other.messageId;

  @override
  int get hashCode => messageId.hashCode;

  @override
  String toString() =>
      'ThreadMessage(id: $messageId, from: $sender, type: $messageType, time: $timestamp)';
}
