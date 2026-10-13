/// Typed failures (§72). User-facing messages are friendly — never stack traces.
abstract class Failure implements Exception {
  const Failure(this.message);
  final String message;

  @override
  String toString() => message;
}

class NetworkFailure extends Failure {
  const NetworkFailure() : super('Network error — please check your connection.');
}

class UnauthorizedFailure extends Failure {
  const UnauthorizedFailure(super.message);
}

class ForbiddenFailure extends Failure {
  const ForbiddenFailure(super.message);
}

class NotFoundFailure extends Failure {
  const NotFoundFailure(super.message);
}

class ValidationFailure extends Failure {
  const ValidationFailure(super.message);
}

class RateLimitFailure extends Failure {
  const RateLimitFailure() : super('Too many requests. Please retry later.');
}

class ServerFailure extends Failure {
  const ServerFailure(super.message);
}

class SyncFailure extends Failure {
  const SyncFailure(super.message);
}
