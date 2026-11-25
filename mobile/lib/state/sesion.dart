import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models.dart';
import '../services/api.dart';

/// Estado de sesión: guarda el token JWT y el usuario actual.
class Sesion extends ChangeNotifier {
  final Api api;
  Usuario? usuario;
  bool cargando = true;
  String? avisoSesion;

  Sesion(this.api) {
    api.alExpirarSesion = () => cerrar(aviso: 'Tu sesión expiró. Inicia sesión de nuevo.');
  }

  bool get autenticado => api.token != null && usuario != null;

  Future<void> restaurar() async {
    final prefs = await SharedPreferences.getInstance();
    api.token = prefs.getString('token');
    if (api.token != null) {
      try {
        usuario = await api.perfil();
      } catch (_) {
        api.token = null;
        await prefs.remove('token');
      }
    }
    cargando = false;
    notifyListeners();
  }

  Future<void> _guardar(String token, Usuario u) async {
    api.token = token;
    usuario = u;
    avisoSesion = null;
    (await SharedPreferences.getInstance()).setString('token', token);
    notifyListeners();
  }

  Future<void> login(String email, String password) async {
    final (t, u) = await api.login(email, password);
    await _guardar(t, u);
  }

  Future<void> registro(String nombre, String email, String password) async {
    final (t, u) = await api.registro(nombre, email, password);
    await _guardar(t, u);
  }

  void actualizarUsuario(Usuario u) {
    usuario = u;
    notifyListeners();
  }

  Future<void> cerrar({String? aviso}) async {
    api.token = null;
    usuario = null;
    avisoSesion = aviso;
    (await SharedPreferences.getInstance()).remove('token');
    notifyListeners();
  }
}
