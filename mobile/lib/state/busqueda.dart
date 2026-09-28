import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../config.dart';
import '../models.dart';
import '../services/api.dart';

/// Estado compartido por Mapa y Lista: destino, radio, orden, filtros y resultados.
class Busqueda extends ChangeNotifier {
  final Api api;
  Busqueda(this.api);

  Position? miUbicacion;
  String? errorUbicacion;
  Destino? destino;

  double radio = Config.radioDefecto;
  String orden = 'distancia'; // distancia | tarifa | calificacion
  double? tarifaMin;
  double? tarifaMax;

  List<Parqueadero> resultados = [];
  String? mensaje;
  bool sugerirAmpliar = false;
  bool cargando = false;
  String? error;

  double get lat => destino?.latitud ?? miUbicacion?.latitude ?? Config.bogotaLat;
  double get lon => destino?.longitud ?? miUbicacion?.longitude ?? Config.bogotaLon;
  bool get tieneReferencia => destino != null || miUbicacion != null;

  /// HU 4: solicitar permiso y capturar coordenadas.
  Future<void> obtenerUbicacion() async {
    errorUbicacion = null;
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        errorUbicacion = 'Activa el GPS del teléfono para usar tu ubicación.';
      } else {
        var permiso = await Geolocator.checkPermission();
        if (permiso == LocationPermission.denied) permiso = await Geolocator.requestPermission();
        if (permiso == LocationPermission.denied || permiso == LocationPermission.deniedForever) {
          errorUbicacion = 'Permiso de ubicación rechazado. Actívalo manualmente en la configuración del teléfono.';
        } else {
          miUbicacion = await Geolocator.getCurrentPosition();
          destino = null;
        }
      }
    } catch (_) {
      errorUbicacion = 'No fue posible obtener tu ubicación.';
    }
    notifyListeners();
    if (miUbicacion != null) await buscar();
  }

  /// HU 5: fijar destino por dirección o nombre.
  Future<String?> buscarDestino(String texto) async {
    if (texto.trim().isEmpty) return 'Escribe una dirección o lugar';
    try {
      destino = await api.geocodificar(texto.trim());
      notifyListeners();
      await buscar();
      return null;
    } on ApiException catch (e) {
      return e.codigo == 'destino_no_encontrado' ? 'Destino no encontrado' : e.mensaje;
    }
  }

  void fijarDestino(Destino d) {
    destino = d;
    notifyListeners();
    buscar();
  }

  Future<void> buscar() async {
    cargando = true;
    error = null;
    notifyListeners();
    try {
      final r = await api.buscar(
          lat: lat, lon: lon, radio: radio, orden: orden, tarifaMin: tarifaMin, tarifaMax: tarifaMax);
      resultados = r.parqueaderos;
      mensaje = r.mensaje;
      sugerirAmpliar = r.sugerirAmpliar;
    } on ApiException catch (e) {
      error = e.mensaje;
      resultados = [];
    } finally {
      cargando = false;
      notifyListeners();
    }
  }

  void cambiarRadio(double r) {
    radio = r.clamp(Config.radioMin, Config.radioMax);
    notifyListeners();
  }

  void cambiarOrden(String o) {
    orden = o;
    buscar();
  }

  void cambiarRangoTarifa(double? min, double? max) {
    tarifaMin = min;
    tarifaMax = max;
    buscar();
  }
}
