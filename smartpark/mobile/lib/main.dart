import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'services/api.dart';
import 'state/busqueda.dart';
import 'state/sesion.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('es');
  final api = Api();
  runApp(MultiProvider(
    providers: [
      Provider.value(value: api),
      ChangeNotifierProvider(create: (_) => Sesion(api)..restaurar()),
      ChangeNotifierProvider(create: (_) => Busqueda(api)),
    ],
    child: const SmartParkApp(),
  ));
}

class SmartParkApp extends StatelessWidget {
  const SmartParkApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SmartPark',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF1F6FEB),
        useMaterial3: true,
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      home: Consumer<Sesion>(
        builder: (_, s, __) {
          if (s.cargando) return const Scaffold(body: Center(child: CircularProgressIndicator()));
          return s.autenticado ? const HomeScreen() : const LoginScreen();
        },
      ),
    );
  }
}
