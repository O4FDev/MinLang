#ifndef MINYAR_FREESTANDING_MATH_H
#define MINYAR_FREESTANDING_MATH_H
#define isnan(x) __builtin_isnan(x)
#define isinf(x) __builtin_isinf(x)
#define isfinite(x) __builtin_isfinite(x)
#define signbit(x) __builtin_signbit(x)
#define HUGE_VAL __builtin_huge_val()
#define INFINITY __builtin_inff()
#define NAN __builtin_nanf("")
double sqrt(double); double sin(double); double cos(double); double tan(double);
double asin(double); double acos(double); double atan(double); double atan2(double, double);
double exp(double); double log(double); double pow(double, double);
double floor(double); double ceil(double); double round(double); double trunc(double);
double fabs(double); double fmod(double, double); double ldexp(double, int); double frexp(double, int *);
#endif
