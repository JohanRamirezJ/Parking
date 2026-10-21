import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/busqueda.dart';
import 'chat_screen.dart';
import 'lista_screen.dart';
import 'mapa_screen.dart';
import 'perfil_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    // HU 4: al abrir la app se solicita la ubicación
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final b = context.read<Busqueda>();
      if (!b.tieneReferencia) b.obtenerUbicacion();
    });
  }

  @override
  Widget build(BuildContext context) {
    final paginas = [
      MapaScreen(onVerLista: () => setState(() => _tab = 1)),
      const ListaScreen(),
      ChatScreen(onVerEnMapa: () => setState(() => _tab = 0)),
      const PerfilScreen(),
    ];
    return Scaffold(
      body: IndexedStack(index: _tab, children: paginas),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.map_outlined), selectedIcon: Icon(Icons.map), label: 'Mapa'),
          NavigationDestination(icon: Icon(Icons.compare_arrows), label: 'Comparar'),
          NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline), selectedIcon: Icon(Icons.chat_bubble), label: 'Asistente'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Perfil'),
        ],
      ),
    );
  }
}
