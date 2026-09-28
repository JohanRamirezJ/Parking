import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../models.dart';

class ApiException implements Exception {
  final int status;
  final String codigo;
  final String mensaje;
  final Map<String, dynamic> detalles;
  ApiException(this.status, this.codigo, this.mensaje, [this.detalles = const {}]);
  @override
  String toString() => mensaje;
}

/// Cliente HTTP del backend Flask. Añade el token JWT (HU 13) y convierte
/// cualquier error en un ApiException con mensaje en español (RF-07).
class Api {
  String? token;

  /// Se invoca cuando el backend responde 401 → la app vuelve al login.
  void Function()? alExpirarSesion;

  final http.Client _http = http.Client();
  static const _timeout = Duration(seconds: 10);

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Uri _uri(String ruta, [Map<String, dynamic>? q]) {
    final params = <String, String>{};
    q?.forEach((k, v) {
      if (v != null) params[k] = v.toString();
    });
    final base = Uri.parse('${Config.apiUrl}/api$ruta');
    return params.isEmpty ? base : base.replace(queryParameters: params);
  }

  Future<dynamic> _enviar(Future<http.Response> Function() req) async {
    http.Response r;
    try {
      r = await req().timeout(_timeout);
    } on TimeoutException {
      throw ApiException(0, 'timeout', 'El servidor tardó demasiado en responder. Intenta de nuevo.');
    } on SocketException {
      throw ApiException(0, 'sin_conexion', 'No hay conexión con el servidor. Revisa tu internet.');
    } on http.ClientException {
      throw ApiException(0, 'sin_conexion', 'No hay conexión con el servidor. Revisa tu internet.');
    }
    final cuerpo = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 200 && r.statusCode < 300) return cuerpo;

    final err = (cuerpo is Map && cuerpo['error'] is Map) ? cuerpo['error'] as Map : const {};
    final ex = ApiException(r.statusCode, err['codigo'] ?? 'error', err['mensaje'] ?? 'Error inesperado (${r.statusCode})',
        Map<String, dynamic>.from(err['detalles'] ?? {}));
    if (r.statusCode == 401 && token != null) alExpirarSesion?.call();
    throw ex;
  }

  Future<dynamic> get(String ruta, [Map<String, dynamic>? q]) => _enviar(() => _http.get(_uri(ruta, q), headers: _headers));
  Future<dynamic> post(String ruta, [Object? body]) =>
      _enviar(() => _http.post(_uri(ruta), headers: _headers, body: jsonEncode(body ?? {})));
  Future<dynamic> put(String ruta, [Object? body]) =>
      _enviar(() => _http.put(_uri(ruta), headers: _headers, body: jsonEncode(body ?? {})));

  // ---------- Auth / perfil ----------
  Future<(String, Usuario)> login(String email, String password) async {
    final d = await post('/auth/login', {'email': email, 'password': password});
    return (d['token'] as String, Usuario.fromJson(d['usuario']));
  }

  Future<(String, Usuario)> registro(String nombre, String email, String password) async {
    final d = await post('/auth/registro', {'nombre': nombre, 'email': email, 'password': password});
    return (d['token'] as String, Usuario.fromJson(d['usuario']));
  }

  Future<Usuario> perfil() async => Usuario.fromJson(await get('/me'));
  Future<Usuario> editarPerfil(Map<String, dynamic> cambios) async => Usuario.fromJson(await put('/me', cambios));
  Future<List<dynamic>> notificaciones() async => await get('/me/notificaciones') as List<dynamic>;

  // ---------- Búsqueda ----------
  Future<Destino> geocodificar(String q) async {
    final d = await get('/geocodificar', {'q': q});
    return Destino(d['nombre'], (d['latitud'] as num).toDouble(), (d['longitud'] as num).toDouble());
  }

  Future<ResultadoBusqueda> buscar({
    required double lat,
    required double lon,
    required double radio,
    String orden = 'distancia',
    double? tarifaMin,
    double? tarifaMax,
  }) async {
    final d = await get('/parqueaderos', {
      'lat': lat,
      'lon': lon,
      'radio': radio.round(),
      'orden': orden,
      'tarifa_min': tarifaMin,
      'tarifa_max': tarifaMax,
    });
    return ResultadoBusqueda(
      (d['resultados'] as List).map((e) => Parqueadero.fromJson(e)).toList(),
      d['mensaje'],
      d['sugerir_ampliar_radio'] == true,
    );
  }

  Future<Parqueadero> parqueadero(int id, {double? lat, double? lon}) async =>
      Parqueadero.fromJson(await get('/parqueaderos/$id', {'lat': lat, 'lon': lon}));

  // ---------- Reseñas ----------
  Future<List<Resena>> resenas(int id) async {
    final d = await get('/parqueaderos/$id/resenas');
    return (d['resenas'] as List).map((e) => Resena.fromJson(e)).toList();
  }

  Future<void> marcarVisitado(int id) => post('/parqueaderos/$id/visitas');

  Future<double?> calificar(int id, int calificacion, String comentario) async {
    final d = await post('/parqueaderos/$id/resenas', {'calificacion': calificacion, 'comentario': comentario});
    return (d['calificacion_promedio'] as num?)?.toDouble();
  }

  Future<void> reportarResena(int resenaId, String motivo) => post('/resenas/$resenaId/reportar', {'motivo': motivo});

  // ---------- Chat IA ----------
  Future<Map<String, dynamic>> chat(String mensaje, {double? lat, double? lon}) async =>
      Map<String, dynamic>.from(await post('/chat', {'mensaje': mensaje, 'lat': lat, 'lon': lon}));
}

class ResultadoBusqueda {
  final List<Parqueadero> parqueaderos;
  final String? mensaje;
  final bool sugerirAmpliar;
  ResultadoBusqueda(this.parqueaderos, this.mensaje, this.sugerirAmpliar);
}
