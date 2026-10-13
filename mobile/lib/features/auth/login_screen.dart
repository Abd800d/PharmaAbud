/// Login screen (§45) + AuthRepository (data layer).
/// Local browsing works without an account; sign-in enables sync, favorites
/// backup and contribution workflows.
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/config/app_config.dart';
import '../../core/errors/failures.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/network/api_client.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';

/// Auth repository — wraps /auth endpoints and secure-ish token persistence.
class AuthRepository {
  AuthRepository({ApiClient? api}) : _api = api ?? ApiClient();

  final ApiClient _api;

  Future<String> login(String email, String password) async {
    final data = await _api.post('/auth/login', body: {'email': email, 'password': password});
    return (data['access_token'] ?? '') as String;
  }

  Future<void> saveToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
    _api.token = token;
  }

  Future<bool> hasSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('auth_token') ?? '';
    _api.token = token.isNotEmpty ? token : null;
    return token.isNotEmpty;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    _api.token = null;
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.onDone});

  final VoidCallback onDone;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _auth = AuthRepository();
  bool _busy = false;
  String _error = '';

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final t = AppLocalizations.of(context);
    setState(() { _busy = true; _error = ''; });
    try {
      final token = await _auth.login(_email.text.trim(), _password.text);
      await _auth.saveToken(token);
      widget.onDone();
    } on Failure catch (f) {
      setState(() => _error = f.message);
    } catch (_) {
      setState(() => _error = t.tr('networkError'));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('settings')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AphSpacing.lg),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Container(
              width: 84, height: 84,
              decoration: BoxDecoration(color: AphColors.navy, borderRadius: BorderRadius.circular(22)),
              child: const Center(
                child: Text('APH',
                    style: TextStyle(color: AphColors.cyanAccent, fontSize: 24, fontWeight: FontWeight.w800)),
              ),
            ),
            const SizedBox(height: AphSpacing.md),
            Text(t.tr('appTitle'), style: Theme.of(context).textTheme.headlineSmall),
            Text(t.tr('appTitleArabic'),
                textDirection: TextDirection.rtl,
                style: const TextStyle(color: AphColors.textSecondary)),
            const SizedBox(height: AphSpacing.xl),
            TextField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.email_outlined)),
            ),
            const SizedBox(height: AphSpacing.md),
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Password', prefixIcon: Icon(Icons.lock_outline)),
            ),
            const SizedBox(height: AphSpacing.lg),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _busy ? null : _login,
                child: _busy
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Sign in'),
              ),
            ),
            if (_error.isNotEmpty) ...[
              const SizedBox(height: AphSpacing.md),
              Text(_error, style: const TextStyle(color: AphColors.red)),
            ],
            const SizedBox(height: AphSpacing.md),
            TextButton(
              onPressed: widget.onDone,
              child: Text(t.tr('home')),
            ),
            const SizedBox(height: AphSpacing.xl),
            Text(AppConfig.copyright,
                style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
          ]),
        ),
      ),
    );
  }
}
