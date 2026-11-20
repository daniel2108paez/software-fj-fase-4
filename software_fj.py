"""Software FJ | Programación 213023 | Fase 4.
Ejecutar: python software_fj.py
Los datos viven en memoria. El archivo software_fj.log registra cada operación.
"""

import logging
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from re import fullmatch
from typing import overload


class ErrorSoftwareFJ(Exception):
    """Error previsto que puede comunicarse sin detener la simulación."""


class DatosInvalidos(ErrorSoftwareFJ):
    """Un dato obligatorio falta o tiene un valor inválido."""


class OperacionNoPermitida(ErrorSoftwareFJ):
    """El estado actual impide completar la operación."""


class ErrorCalculo(ErrorSoftwareFJ):
    """El costo solicitado no se puede calcular."""


def texto(valor, campo):
    """Normaliza texto obligatorio y rechaza valores vacíos."""
    if not isinstance(valor, str) or not valor.strip():
        raise DatosInvalidos(f"{campo} es obligatorio.")
    return valor.strip()


def entero_positivo(valor, campo):
    """Exige un entero positivo y excluye los valores booleanos."""
    if type(valor) is not int or valor < 1:
        raise DatosInvalidos(f"{campo} debe ser un entero positivo.")
    return valor


def decimal_finito(valor, campo):
    """Convierte un dato decimal y conserva la causa de errores de conversión."""
    try:
        numero = Decimal(str(valor))
    except InvalidOperation as error:
        raise DatosInvalidos(f"{campo} debe ser numérico.") from error
    if not numero.is_finite():
        raise DatosInvalidos(f"{campo} debe ser finito.")
    return numero


class Entidad(ABC):
    """Define el identificador y el contrato común para las entidades."""

    def __init__(self, identificador):
        # Conserva el mismo formato para buscar y detectar duplicados.
        self._identificador = texto(identificador, "Identificador").upper()

    @property
    def identificador(self):
        """Expone el identificador sin permitir su reasignación pública."""
        return self._identificador

    @abstractmethod
    def describir(self):
        """Devuelve un resumen breve de la entidad."""


class Cliente(Entidad):
    """Protege y valida los datos de contacto al registrar un cliente."""

    def __init__(self, identificador, nombre, correo, telefono):
        super().__init__(identificador)
        self.__nombre = texto(nombre, "Nombre")
        self.__correo = texto(correo, "Correo").lower()
        self.__telefono = texto(telefono, "Teléfono")
        # Aplica validaciones de formato y evita guardar contacto incompleto.
        if not fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.__correo):
            raise DatosInvalidos("Correo inválido.")
        if not fullmatch(r"\+?[0-9]{7,15}", self.__telefono):
            raise DatosInvalidos("El teléfono debe tener de 7 a 15 dígitos.")

    @property
    def correo(self):
        """Expone el correo para detectar contactos duplicados."""
        return self.__correo

    def describir(self):
        """Identifica al cliente en los registros sin exponer su contacto."""
        return f"Cliente {self.identificador}"


class Servicio(Entidad, ABC):
    """Define el contrato de validación y cálculo para cada tipo de servicio."""

    def __init__(self, identificador, nombre, tarifa_hora):
        super().__init__(identificador)
        self._nombre = texto(nombre, "Nombre del servicio")
        self._tarifa_hora = decimal_finito(tarifa_hora, "Tarifa por hora")
        if self._tarifa_hora <= 0:
            raise DatosInvalidos("La tarifa por hora debe ser mayor que cero.")

    @abstractmethod
    def validar_duracion(self, horas):
        """Comprueba las horas permitidas para el servicio."""

    @abstractmethod
    def costo_base(self, horas):
        """Calcula el importe según el servicio concreto."""

    @overload
    def calcular_costo(self, horas: int) -> Decimal: ...

    @overload
    def calcular_costo(
        self, horas: int, *, impuesto: Decimal | int | str
    ) -> Decimal: ...

    @overload
    def calcular_costo(
        self, horas: int, *, descuento: Decimal | int | str,
        impuesto: Decimal | int | str = 0
    ) -> Decimal: ...

    def calcular_costo(self, horas, *, impuesto=0, descuento=0):
        """Admite solo horas, horas con impuesto, o descuento e impuesto."""
        try:
            # Aplica el descuento primero y calcula el impuesto sobre el saldo.
            descuento = decimal_finito(descuento, "Descuento")
            impuesto = decimal_finito(impuesto, "Impuesto")
            if not 0 <= descuento <= 100 or not 0 <= impuesto <= 100:
                raise DatosInvalidos("Los porcentajes deben estar entre 0 y 100.")
            subtotal = self.costo_base(horas)
            total = subtotal * (1 - descuento / 100) * (1 + impuesto / 100)
            return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (DatosInvalidos, ArithmeticError) as error:
            raise ErrorCalculo(f"No se pudo calcular el costo: {error}") from error


class Sala(Servicio):
    """Reserva de sala con tarifa por hora y capacidad definida."""

    def __init__(self, identificador, nombre, tarifa_hora, capacidad):
        super().__init__(identificador, nombre, tarifa_hora)
        self._capacidad = entero_positivo(capacidad, "Capacidad de la sala")

    def describir(self):
        return f"Sala {self.identificador} | {self._nombre} | {self._capacidad} personas"

    def validar_duracion(self, horas):
        if entero_positivo(horas, "Duración") > 8:
            raise DatosInvalidos("La sala permite hasta 8 horas.")

    def costo_base(self, horas):
        self.validar_duracion(horas)
        return self._tarifa_hora * horas


class Equipo(Servicio):
    """Alquiler de equipo identificado por un número de serie."""

    def __init__(self, identificador, nombre, tarifa_hora, serie):
        super().__init__(identificador, nombre, tarifa_hora)
        self._serie = texto(serie, "Serie del equipo")

    def describir(self):
        return f"Equipo {self.identificador} | {self._nombre} | serie {self._serie}"

    def validar_duracion(self, horas):
        if entero_positivo(horas, "Duración") > 24:
            raise DatosInvalidos("El alquiler permite hasta 24 horas.")

    def costo_base(self, horas):
        self.validar_duracion(horas)
        # Aplica una rebaja comercial del 10 % desde ocho horas.
        factor = Decimal("0.90") if horas >= 8 else Decimal("1")
        return self._tarifa_hora * horas * factor


class Asesoria(Servicio):
    """Asesoría especializada con un cargo fijo de preparación."""

    def __init__(self, identificador, nombre, tarifa_hora, especialidad):
        super().__init__(identificador, nombre, tarifa_hora)
        self._especialidad = texto(especialidad, "Especialidad")

    def describir(self):
        return f"Asesoría {self.identificador} | {self._nombre} | {self._especialidad}"

    def validar_duracion(self, horas):
        if entero_positivo(horas, "Duración") > 4:
            raise DatosInvalidos("Una asesoría puede durar hasta 4 horas.")

    def costo_base(self, horas):
        self.validar_duracion(horas)
        # Suma el cargo fijo de preparación en pesos colombianos.
        return self._tarifa_hora * horas + Decimal("15000")


class Estado(Enum):
    """Estados admitidos durante el ciclo de una reserva."""

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class Reserva(Entidad):
    """Integra un cliente, un servicio, la duración y el total confirmado."""

    def __init__(self, identificador, cliente, servicio, horas):
        super().__init__(identificador)
        self._cliente = cliente
        self._servicio = servicio
        self._horas = entero_positivo(horas, "Duración")
        self._estado = Estado.PENDIENTE
        self._total = None

    @property
    def servicio(self):
        return self._servicio

    @property
    def estado(self):
        return self._estado

    def confirmar(self, reservas, *, impuesto=0, descuento=0):
        """Confirma y guarda el costo solo si el procesamiento termina."""
        if self.estado is not Estado.PENDIENTE:
            raise OperacionNoPermitida("Solo se puede confirmar una reserva pendiente.")
        # El modelo permite una reserva confirmada por servicio a la vez.
        if any(r.servicio is self.servicio and r.estado is Estado.CONFIRMADA
               for r in reservas):
            raise OperacionNoPermitida("El servicio no está disponible.")
        try:
            total = self.servicio.calcular_costo(
                self._horas, impuesto=impuesto, descuento=descuento
            )
        except ErrorCalculo as error:
            raise OperacionNoPermitida(f"La reserva {self.identificador} falló: {error}") from error
        else:
            self._total = total
            self._estado = Estado.CONFIRMADA
            return self

    def cancelar(self):
        """Cancela la reserva y libera el servicio para otra operación."""
        if self.estado is Estado.CANCELADA:
            raise OperacionNoPermitida("La reserva ya está cancelada.")
        self._estado = Estado.CANCELADA
        return self

    def describir(self):
        resumen = (
            f"Reserva {self.identificador} | cliente {self._cliente.identificador} | "
            f"servicio {self.servicio.identificador} | {self._horas} h | {self.estado.value}"
        )
        if self._total is not None:
            resumen += f" | total histórico COP $ {self._total:,.2f}"
        return resumen


class SistemaReservas:
    """Coordina registros y búsquedas con tres listas privadas en memoria."""

    def __init__(self):
        self.__clientes = []
        self.__servicios = []
        self.__reservas = []

    @staticmethod
    def _buscar(lista, identificador):
        codigo = texto(identificador, "Identificador").upper()
        for entidad in lista:
            if entidad.identificador == codigo:
                return entidad
        raise DatosInvalidos(f"No existe el identificador {codigo}.")

    @staticmethod
    def _guardar(lista, entidad):
        if any(item.identificador == entidad.identificador for item in lista):
            raise OperacionNoPermitida(f"Identificador duplicado: {entidad.identificador}.")
        lista.append(entidad)
        return entidad

    def registrar_cliente(self, *datos):
        cliente = Cliente(*datos)
        if any(item.correo == cliente.correo for item in self.__clientes):
            raise OperacionNoPermitida("Ya existe un cliente con ese correo.")
        return self._guardar(self.__clientes, cliente)

    def registrar_servicio(self, tipo, *datos):
        # Selecciona una de las tres implementaciones del contrato de Servicio.
        clases = {"sala": Sala, "equipo": Equipo, "asesoria": Asesoria}
        tipo = texto(tipo, "Tipo de servicio").lower()
        if tipo not in clases:
            raise DatosInvalidos(f"Tipo de servicio desconocido: {tipo}.")
        return self._guardar(self.__servicios, clases[tipo](*datos))

    def procesar_reserva(self, codigo, cliente_id, servicio_id, horas, **ajustes):
        cliente = self._buscar(self.__clientes, cliente_id)
        servicio = self._buscar(self.__servicios, servicio_id)
        reserva = Reserva(codigo, cliente, servicio, horas)
        # Verifica el ID antes de confirmar y guarda únicamente las reservas exitosas.
        if any(r.identificador == reserva.identificador for r in self.__reservas):
            raise OperacionNoPermitida(f"Reserva duplicada: {reserva.identificador}.")
        reserva.confirmar(self.__reservas, **ajustes)
        return self._guardar(self.__reservas, reserva)

    def cancelar_reserva(self, codigo):
        return self._buscar(self.__reservas, codigo).cancelar()


def ejecutar_caso(numero, titulo, accion, error_esperado, registro):
    """Ejecuta un caso y verifica si coincide con el resultado esperado."""
    prefijo = f"{numero:02d}. {titulo}"
    try:
        resultado = accion()
    except ErrorSoftwareFJ as error:
        registro.exception("%s | error controlado", prefijo)
        coincide = isinstance(error, error_esperado)
        etiqueta = "ERROR ESPERADO" if coincide else "FALLO"
        print(f"{prefijo} → {etiqueta} | {error}")
        return coincide
    except TypeError as error:
        # Indica argumentos faltantes o con nombres que la operación no admite.
        registro.exception("%s | argumentos inválidos", prefijo)
        coincide = error_esperado is TypeError
        etiqueta = "ERROR ESPERADO" if coincide else "FALLO"
        print(f"{prefijo} → {etiqueta} | {error}")
        return coincide
    except Exception as error:
        # Registra una falla imprevista y permite ejecutar los casos restantes.
        registro.exception("%s | error inesperado", prefijo)
        print(f"{prefijo} → FALLO | {error}")
        return False
    else:
        registro.info("%s | %s", prefijo, resultado.describir())
        if error_esperado:
            print(f"{prefijo} → FALLO | Se esperaba un error.")
            return False
        print(f"{prefijo} → OK | {resultado.describir()}")
        return True
    finally:
        # Este evento aparece incluso cuando el caso produjo una excepción.
        registro.info("%s | fin de la operación", prefijo)


def main():
    """Ejecuta la práctica completa con datos ficticios y resultados verificables."""
    ruta_log = Path.cwd() / "software_fj.log"
    registro = logging.getLogger("software_fj")
    registro.setLevel(logging.INFO)
    try:
        destino = logging.FileHandler(ruta_log, encoding="utf-8")
    except OSError as error:
        print(f"No se pudo abrir el archivo de eventos: {error}. Se usará la consola.")
        destino = logging.StreamHandler()
    destino.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    registro.addHandler(destino)
    sistema = SistemaReservas()

    # Cada fila define una acción, su descripción y el error esperado, si corresponde.
    casos = [
        ("Registrar a Laura", lambda: sistema.registrar_cliente("C1", "Laura Gómez", "laura@example.com", "3001112233"), ()),
        ("Rechazar correo inválido", lambda: sistema.registrar_cliente("C2", "Mario Ruiz", "mario.example.com", "3002223344"), DatosInvalidos),
        ("Rechazar cliente duplicado", lambda: sistema.registrar_cliente("C1", "Diego Díaz", "diego@example.com", "3003334455"), OperacionNoPermitida),
        ("Registrar a Mario", lambda: sistema.registrar_cliente("C2", "Mario Ruiz", "mario@example.com", "3002223344"), ()),
        ("Registrar una sala", lambda: sistema.registrar_servicio("sala", "S1", "Sala Norte", 50000, 12), ()),
        ("Registrar un equipo", lambda: sistema.registrar_servicio("equipo", "S2", "Proyector", 30000, "PR-001"), ()),
        ("Registrar una asesoría", lambda: sistema.registrar_servicio("asesoria", "S3", "Consultoría", 80000, "Redes"), ()),
        ("Rechazar tarifa inválida", lambda: sistema.registrar_servicio("sala", "S4", "Sala Sur", "abc", 10), DatosInvalidos),
        ("Detectar un parámetro faltante", lambda: sistema.registrar_servicio("equipo", "S4", "Portátil", 25000), TypeError),
        ("Reservar sala con descuento e impuesto", lambda: sistema.procesar_reserva("R1", "C1", "S1", 2, descuento=10, impuesto=19), ()),
        ("Rechazar reserva por falta de disponibilidad", lambda: sistema.procesar_reserva("R2", "C2", "S1", 1), OperacionNoPermitida),
        ("Rechazar asesoría por duración excesiva", lambda: sistema.procesar_reserva("R3", "C2", "S3", 5), OperacionNoPermitida),
        ("Reservar equipo por ocho horas", lambda: sistema.procesar_reserva("R4", "C2", "S2", 8), ()),
        ("Rechazar descuento fuera de rango", lambda: sistema.procesar_reserva("R3", "C2", "S3", 2, descuento=105), OperacionNoPermitida),
        ("Confirmar asesoría con impuesto", lambda: sistema.procesar_reserva("R3", "C2", "S3", 2, impuesto=19), ()),
        ("Cancelar la reserva de sala", lambda: sistema.cancelar_reserva("R1"), ()),
        ("Rechazar segunda cancelación", lambda: sistema.cancelar_reserva("R1"), OperacionNoPermitida),
        ("Reservar la sala liberada", lambda: sistema.procesar_reserva("R2", "C2", "S1", 1), ()),
        ("Rechazar cliente inexistente", lambda: sistema.procesar_reserva("R5", "C99", "S1", 1), DatosInvalidos),
    ]
    try:
        aprobados = 0
        for numero, (titulo, accion, esperado) in enumerate(casos, start=1):
            aprobados += ejecutar_caso(numero, titulo, accion, esperado, registro)
        resumen = f"{aprobados}/{len(casos)} casos con el resultado esperado."
        print(f"\n{resumen}")
        registro.info(resumen)
        return 0 if aprobados == len(casos) else 1
    finally:
        # Cierra el destino para liberar el archivo incluso si la ejecución se interrumpe.
        registro.removeHandler(destino)
        destino.close()


if __name__ == "__main__":
    raise SystemExit(main())
