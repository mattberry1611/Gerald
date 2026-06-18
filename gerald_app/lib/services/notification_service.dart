import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Placeholder push notification architecture.
/// V1 uses local notifications only; production FCM integration is stubbed.
class NotificationService {
  NotificationService._();
  static final instance = NotificationService._();

  final _plugin = FlutterLocalNotificationsPlugin();
  bool _initialized = false;

  Future<void> init() async {
    if (_initialized) return;

    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);

    await _plugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onTap,
    );

    const channel = AndroidNotificationChannel(
      'gerald_tasks',
      'Gerald Task Notifications',
      description: 'Alerts when Gerald completes a coding task',
      importance: Importance.high,
    );
    final androidImpl = _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.createNotificationChannel(channel);
    // Android 13+ requires a runtime grant for POST_NOTIFICATIONS.
    await androidImpl?.requestNotificationsPermission();

    _initialized = true;
  }

  void _onTap(NotificationResponse response) {
    // Production: navigate to the relevant conversation screen
  }

  Future<void> showTaskComplete(String summary) async {
    await _plugin.show(
      _id(),
      'Gerald: Task Complete',
      summary,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'gerald_tasks',
          'Gerald Task Notifications',
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
    );
  }

  Future<void> showTaskError(String error) async {
    await _plugin.show(
      _id(),
      'Gerald: Error',
      error,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'gerald_tasks',
          'Gerald Task Notifications',
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
    );
  }

  /// Placeholder — wire to firebase_messaging in production.
  /// Register the FCM token with the gerald_bridge /register-device endpoint.
  Future<String?> registerForPushNotifications() async {
    // TODO: final token = await FirebaseMessaging.instance.getToken();
    // TODO: await GeraldApi(baseUrl).registerDevice(token);
    return null;
  }

  int _id() => DateTime.now().millisecondsSinceEpoch ~/ 1000;
}
