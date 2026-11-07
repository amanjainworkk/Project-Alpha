// Project Alpha Mobile APK — Vault Browser Screen
// File Target: Alpha/apk/lib/screens/vault_screen.dart
// Conforms to Feature 76: Document Tree Hierarchy, Episodic Memory Viewer & Vector Search

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../theme/theme.dart';
import '../services/services.dart';

/// Vault Browser Screen featuring document tree hierarchy,
/// vector search bar, episodic memory viewer, and schema overview.
class VaultScreen extends StatefulWidget {
  const VaultScreen({super.key});

  @override
  State<VaultScreen> createState() => _VaultScreenState();
}

class _VaultScreenState extends State<VaultScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _searchController = TextEditingController();
  List<dynamic> _searchResults = [];
  bool _isSearching = false;

  final Map<String, List<String>> _vaultHierarchy = {
    'projects/': [
      'alpha_v1/manifest.json',
      'alpha_v1/brief.json',
      'alpha_v1/deliverables.json',
      'alpha_v1/audit_scorecard.json',
    ],
    'users/': [
      'founder/profile.json',
      'founder/preferences.json',
    ],
    'system/': [
      'company/identity.json',
      'model_router/config.json',
      'agents/registry.json',
    ],
    'audit/': [
      'reports/round_1_consensus.json',
      'compliance/cao_guardrails.json',
    ],
    'memory/': [
      'cto/episodic.jsonl',
      'ceo/episodic.jsonl',
      'cfo/episodic.jsonl',
    ],
  };

  final List<Map<String, dynamic>> _episodicMemories = [
    {
      'agent': 'CTO',
      'type': 'DECISION',
      'timestamp': '2026-11-06 18:24',
      'content': 'Selected SQLite KV + ChromaDB vector embeddings for self-contained desktop Vault.',
      'importance': 9,
      'tags': ['#architecture', '#vault', '#storage'],
    },
    {
      'agent': 'CAO-Claude',
      'type': 'OBSERVATION',
      'timestamp': '2026-11-06 20:15',
      'content': 'Audited model router fallback chain; confirmed Ollama handles offline requests cleanly.',
      'importance': 8,
      'tags': ['#audit', '#compliance', '#fallback'],
    },
    {
      'agent': 'CDO',
      'type': 'LESSON',
      'timestamp': '2026-11-06 21:05',
      'content': 'High-contrast OLED black (#0A0A0F) with electric cyan ensures battery efficiency.',
      'importance': 7,
      'tags': ['#design', '#oled', '#tokens'],
    },
    {
      'agent': 'CEO',
      'type': 'FEEDBACK',
      'timestamp': '2026-11-07 09:30',
      'content': 'Escalation cap strictly enforced at 2 rounds to prevent infinite CAO deliberation loops.',
      'importance': 10,
      'tags': ['#governance', '#cao', '#escalation'],
    },
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _performVectorSearch(String query) async {
    final clean = query.trim();
    if (clean.isEmpty) {
      setState(() {
        _searchResults = [];
        _isSearching = false;
      });
      return;
    }

    setState(() {
      _isSearching = true;
    });

    try {
      final client = context.read<AlphaApiClient?>();
      if (client != null) {
        final results = await client.searchVault(clean, topK: 5);
        if (mounted) {
          setState(() {
            _searchResults = results;
          });
        }
      } else {
        // Fallback local simulated results
        await Future.delayed(const Duration(milliseconds: 300));
        if (mounted) {
          setState(() {
            _searchResults = [
              {
                'id': 'doc_001',
                'text': 'VaultManager schema: SQLite KV + ChromaDB persistence engine.',
                'metadata': {'path': 'system/company/identity.json', 'score': 0.94},
              },
              {
                'id': 'doc_002',
                'text': 'Dual CAO verification engine with Claude & GPT instances.',
                'metadata': {'path': 'audit/compliance/cao_guardrails.json', 'score': 0.88},
              },
            ];
          });
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _searchResults = [];
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSearching = false;
        });
      }
    }
  }

  void _showDocumentPreview(BuildContext context, String path) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaColors.surfaceLevel1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        side: BorderSide(color: AlphaColors.border),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AlphaColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  const Icon(Icons.description, color: AlphaColors.primaryCyan),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      path,
                      style: AlphaTheme.monoStyle.copyWith(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: AlphaColors.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
              const Divider(color: AlphaColors.borderSubtle, height: 20),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AlphaColors.backgroundOled,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AlphaColors.borderSubtle),
                ),
                child: Text(
                  '{\n  "path": "$path",\n  "status": "persisted",\n  "encryption": "aes-256",\n  "schema_version": "1.0.0",\n  "access_tier": "C-Suite Internal"\n}',
                  style: AlphaTheme.monoStyle.copyWith(fontSize: 12),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.close, size: 16),
                  label: const Text('Close Preview'),
                  onPressed: () => Navigator.pop(context),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AlphaColors.backgroundOled,
      body: Column(
        children: [
          // 1. Vector Search Bar
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              style: const TextStyle(fontSize: 13, color: AlphaColors.textPrimary),
              decoration: InputDecoration(
                hintText: 'Semantic Vector Search across Vault...',
                hintStyle: const TextStyle(color: AlphaColors.textMuted, fontSize: 13),
                prefixIcon: const Icon(Icons.manage_search, color: AlphaColors.primaryCyan),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          _performVectorSearch('');
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                fillColor: AlphaColors.surfaceLevel1,
                filled: true,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: AlphaColors.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: AlphaColors.border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: AlphaColors.primaryCyan, width: 1.5),
                ),
              ),
              onSubmitted: _performVectorSearch,
            ),
          ),

          // Vector Search Results Preview if active
          if (_searchResults.isNotEmpty) ...[
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AlphaColors.surfaceLevel1,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AlphaColors.primaryCyan.withOpacity(0.5)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'VECTOR SEARCH RESULTS (${_searchResults.length})',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: AlphaColors.primaryCyan,
                    ),
                  ),
                  const SizedBox(height: 6),
                  ..._searchResults.map((res) {
                    final text = res['text']?.toString() ?? '';
                    final path = res['metadata']?['path']?.toString() ?? '';
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          const Icon(Icons.arrow_right, color: AlphaColors.primaryCyan),
                          Expanded(
                            child: Text(
                              '$path: $text',
                              style: AlphaTheme.monoStyle.copyWith(fontSize: 11),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
            const SizedBox(height: 8),
          ],

          // 2. Segmented Navigation Tab Bar
          TabBar(
            controller: _tabController,
            indicatorColor: AlphaColors.primaryCyan,
            labelColor: AlphaColors.primaryCyan,
            unselectedLabelColor: AlphaColors.textSecondary,
            tabs: const [
              Tab(text: 'Hierarchy Tree'),
              Tab(text: 'Episodic Memory'),
              Tab(text: 'Architecture'),
            ],
          ),

          // 3. Tab Views
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                // Tab 1: Hierarchy Tree View
                ListView(
                  padding: const EdgeInsets.all(16),
                  children: _vaultHierarchy.entries.map((entry) {
                    return Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      decoration: AlphaColors.oledCardDecoration(
                        surfaceColor: AlphaColors.surfaceLevel2,
                        borderColor: AlphaColors.border,
                      ),
                      child: ExpansionTile(
                        leading: const Icon(Icons.folder, color: AlphaColors.primaryCyan),
                        title: Text(
                          entry.key,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AlphaColors.textPrimary,
                          ),
                        ),
                        subtitle: Text(
                          '${entry.value.length} documents',
                          style: const TextStyle(fontSize: 11, color: AlphaColors.textMuted),
                        ),
                        children: entry.value.map((docPath) {
                          return ListTile(
                            dense: true,
                            leading: const Icon(Icons.insert_drive_file, size: 16, color: AlphaColors.secondaryBlue),
                            title: Text(
                              docPath,
                              style: AlphaTheme.monoStyle.copyWith(fontSize: 12),
                            ),
                            trailing: const Icon(Icons.chevron_right, size: 16, color: AlphaColors.textMuted),
                            onTap: () => _showDocumentPreview(context, '${entry.key}$docPath'),
                          );
                        }).toList(),
                      ),
                    );
                  }).toList(),
                ),

                // Tab 2: Episodic Memory Viewer
                ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _episodicMemories.length,
                  itemBuilder: (context, index) {
                    final mem = _episodicMemories[index];
                    return Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.all(14),
                      decoration: AlphaColors.oledCardDecoration(
                        surfaceColor: AlphaColors.surfaceLevel2,
                        borderColor: AlphaColors.border,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: AlphaColors.surfaceLevel3,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      mem['agent'],
                                      style: const TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: AlphaColors.primaryCyan,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: AlphaColors.statusBadgeDecoration(
                                      statusColor: AlphaColors.secondaryBlue,
                                    ),
                                    child: Text(
                                      mem['type'],
                                      style: const TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: AlphaColors.secondaryBlue,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              Text(
                                mem['timestamp'],
                                style: AlphaTheme.monoStyle.copyWith(fontSize: 10),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            mem['content'],
                            style: const TextStyle(fontSize: 13, color: AlphaColors.textPrimary),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 6,
                            children: (mem['tags'] as List<String>).map((tag) {
                              return Text(
                                tag,
                                style: AlphaTheme.monoStyle.copyWith(
                                  fontSize: 11,
                                  color: AlphaColors.primaryCyanNeon,
                                ),
                              );
                            }).toList(),
                          ),
                        ],
                      ),
                    );
                  },
                ),

                // Tab 3: Architecture Diagram & Schemas Overview
                ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: AlphaColors.oledCardDecoration(
                        surfaceColor: AlphaColors.surfaceLevel2,
                        borderColor: AlphaColors.border,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.hub, color: AlphaColors.primaryCyan),
                              SizedBox(width: 8),
                              Text(
                                'ARCHITECTURAL TOPOLOGY',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: AlphaColors.primaryCyan,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            '• Desktop Backend: FastAPI REST + WebSocket telemetry (localhost:8765)\n'
                            '• Vault Store: SQLite key-value + ChromaDB embeddings\n'
                            '• Model Router: Complexity tiers 1-5 with Ollama local fallback\n'
                            '• Dual CAO Audit Gate: Claude & GPT cross-validation with 2-round cap\n'
                            '• Mobile Companion: Flutter APK living canvas & OLED command center',
                            style: TextStyle(fontSize: 13, color: AlphaColors.textSecondary, height: 1.5),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
