/* The http package on macOS: requests run on NSURLSession, which validates
 * TLS certificates, follows redirects, negotiates HTTP/2 and keeps cookies for
 * the application. Compile with ARC. Requests are checked Integer handles;
 * their bodies are buffered here until the program reads them. */
#import <AppKit/AppKit.h>
#include <limits.h>
#include <math.h>
#include <stdatomic.h>
#include "../minyar_native.h"
#include "apple_identity.h"

/* Matches MNWakeSubtype in macos.m: ends a macos.nextEvent wait. */
enum { MHWakeSubtype = 0x4D59 };

@interface MHRequest : NSObject
@property(nonatomic, strong) NSURLSessionDataTask *task;
@property(nonatomic, strong) NSMutableData *unread;
@property(nonatomic, strong) NSHTTPURLResponse *response;
@property(nonatomic, copy) NSString *error;
@property(nonatomic) BOOL done;
@property(nonatomic, strong) NSCondition *condition;
@property(nonatomic, strong) NSURLCredential *clientCredential;
@property(nonatomic, strong) NSURL *credentialOrigin;
@property(nonatomic, strong) NSURLSession *identitySession;
@end
@implementation MHRequest
@end
@interface MHDelegate : NSObject <NSURLSessionDataDelegate>
@end

static NSURLSession *session;
static NSMutableDictionary<NSNumber *, MHRequest *> *requests;
static NSMapTable<NSURLSessionTask *, MHRequest *> *byTask;
static long long nextRequest = 1;
static atomic_bool wakePending;
static void http_owner(void) {
    if (![NSThread isMainThread]) minyar_native_stop("http APIs require the main thread.");
}

/* Wake a waiting desktop event loop, at most once until the program next looks. */
static void wake(void) {
    if (!NSApp || atomic_exchange(&wakePending, true)) return;
    NSEvent *e = [NSEvent otherEventWithType:NSEventTypeApplicationDefined location:NSZeroPoint modifierFlags:0
        timestamp:0 windowNumber:0 context:nil subtype:MHWakeSubtype data1:0 data2:0];
    [NSApp postEvent:e atStart:NO];
}
static MHRequest *requestFor(NSURLSessionTask *task) {
    @synchronized(byTask) { return [byTask objectForKey:task]; }
}
static void finish(MHRequest *r, NSString *error) {
    [r.condition lock];
    if (!r.done) { r.done = YES; if (error && !r.error) r.error = error; }
    [r.condition broadcast];
    [r.condition unlock];
    wake();
}

static BOOL http_same_origin(NSURL *a, NSURL *b) {
    return a.host.length && b.host.length && [a.scheme.lowercaseString isEqualToString:@"https"] &&
        [b.scheme.lowercaseString isEqualToString:@"https"] &&
        [a.host caseInsensitiveCompare:b.host]==NSOrderedSame &&
        (a.port?a.port.integerValue:443)==(b.port?b.port.integerValue:443) && !b.user && !b.password;
}
static NSURLCredential *http_identity_credential(const MinyarBytes *reference, const MinyarBytes *chain) {
    SecIdentityRef identity=identity_value(reference);
    if (!identity) return nil;
    NSMutableArray *certificates=[NSMutableArray new];
    BOOL valid=chain->byte_length>=0 && chain->byte_length<=1048576;
    size_t offset=0;
    if (valid && chain->byte_length) {
        valid=chain->byte_length>=4;
        uint32_t count=valid?identity_word(chain->bytes):0;
        valid=valid && count<=16; offset=4;
        for (uint32_t i=0;valid && i<count;i++) {
            if ((uint64_t)chain->byte_length-offset<4) { valid=NO; break; }
            uint32_t size=identity_word(chain->bytes+offset); offset+=4;
            if (!size || size>(uint64_t)chain->byte_length-offset) { valid=NO; break; }
            CFDataRef data=CFDataCreate(NULL,chain->bytes+offset,size);
            SecCertificateRef cert=data?SecCertificateCreateWithData(NULL,data):NULL;
            if (data) CFRelease(data);
            if (!cert) { valid=NO; break; }
            [certificates addObject:CFBridgingRelease(cert)]; offset+=size;
        }
        valid=valid && offset==(uint64_t)chain->byte_length;
    }
    NSURLCredential *credential=valid?[NSURLCredential credentialWithIdentity:identity
        certificates:certificates.count?certificates:nil persistence:NSURLCredentialPersistenceForSession]:nil;
    CFRelease(identity); return credential;
}
static void http_authenticate(MHRequest *r, NSURLAuthenticationChallenge *challenge,
                              void (^handler)(NSURLSessionAuthChallengeDisposition,NSURLCredential *)) {
    NSURLProtectionSpace *space=challenge.protectionSpace;
    if (![space.authenticationMethod isEqualToString:NSURLAuthenticationMethodClientCertificate] || !r.clientCredential) {
        handler(NSURLSessionAuthChallengePerformDefaultHandling,nil); return;
    }
    [r.condition lock]; BOOL done=r.done; [r.condition unlock];
    NSURL *origin=r.credentialOrigin;
    BOOL match=!done && space.host.length && origin.host.length && !space.isProxy && !challenge.previousFailureCount &&
        [space.protocol.lowercaseString isEqualToString:@"https"] &&
        [space.host caseInsensitiveCompare:origin.host]==NSOrderedSame &&
        space.port==(origin.port?origin.port.integerValue:443);
    handler(match?NSURLSessionAuthChallengeUseCredential:NSURLSessionAuthChallengeCancelAuthenticationChallenge,
            match?r.clientCredential:nil);
}

@implementation MHDelegate
- (void)URLSession:(NSURLSession *)s task:(NSURLSessionTask *)task didReceiveChallenge:(NSURLAuthenticationChallenge *)challenge
    completionHandler:(void (^)(NSURLSessionAuthChallengeDisposition,NSURLCredential *))handler {
    (void)s; http_authenticate(requestFor(task),challenge,handler);
}
- (void)URLSession:(NSURLSession *)s task:(NSURLSessionTask *)task willPerformHTTPRedirection:(NSHTTPURLResponse *)response
    newRequest:(NSURLRequest *)request completionHandler:(void (^)(NSURLRequest *))handler {
    (void)s; (void)response; MHRequest *r=requestFor(task);
    if (r.clientCredential && !http_same_origin(r.credentialOrigin,request.URL)) {
        finish(r,@"client certificate requests cannot redirect to another origin"); handler(nil);
    } else handler(request);
}
- (void)URLSession:(NSURLSession *)s dataTask:(NSURLSessionDataTask *)task didReceiveResponse:(NSURLResponse *)response
    completionHandler:(void (^)(NSURLSessionResponseDisposition))handler {
    (void)s;
    MHRequest *r = requestFor(task);
    if (r && [response isKindOfClass:NSHTTPURLResponse.class]) {
        [r.condition lock]; r.response = (NSHTTPURLResponse *)response; [r.condition unlock];
        wake();
    }
    handler(NSURLSessionResponseAllow);
}
- (void)URLSession:(NSURLSession *)s dataTask:(NSURLSessionDataTask *)task didReceiveData:(NSData *)data {
    (void)s;
    MHRequest *r = requestFor(task);
    if (!r) return;
    [r.condition lock]; [r.unread appendData:data]; [r.condition unlock];
    wake();
}
- (void)URLSession:(NSURLSession *)s task:(NSURLSessionTask *)task didCompleteWithError:(NSError *)error {
    (void)s;
    MHRequest *r = requestFor(task);
    if (!r) return;
    NSString *message = nil;
    if (error) message = error.code == NSURLErrorCancelled ? @"cancelled" : error.localizedDescription;
    finish(r, message);
    @synchronized(byTask) { [byTask removeObjectForKey:task]; }
    [r.identitySession finishTasksAndInvalidate]; r.identitySession=nil;
}
@end

static NSString *string(const MinyarText *text) {
    NSString *s = [[NSString alloc] initWithBytes:text->bytes length:(NSUInteger)text->byte_length encoding:NSUTF8StringEncoding];
    if (!s) minyar_native_stop("http requires valid UTF-8 Text.");
    return s;
}
static MinyarText *owned(NSString *s) {
    NSData *data = [(s ?: @"") dataUsingEncoding:NSUTF8StringEncoding];
    return minyar_native_copy_text(data.bytes, (long long)data.length);
}
static MHRequest *entry(long long handle) {
    http_owner();
    MHRequest *r = requests[@(handle)];
    if (!r) minyar_native_stop("http received an invalid or closed request.");
    return r;
}
/* Length of the longest prefix that does not end inside a UTF-8 sequence. */
static size_t completeUTF8(const unsigned char *bytes, size_t length) {
    size_t back = 0;
    while (back < length && back < 4 && (bytes[length - 1 - back] & 0xC0) == 0x80) back++;
    if (back == length) return length;
    unsigned char lead = bytes[length - 1 - back];
    size_t need = lead < 0x80 ? 1 : (lead & 0xE0) == 0xC0 ? 2 : (lead & 0xF0) == 0xE0 ? 3 : (lead & 0xF8) == 0xF0 ? 4 : 1;
    return back + 1 < need ? length - 1 - back : length;
}
/* Copy UTF-8, replacing malformed sequences with U+FFFD, into an owned Text. */
static MinyarText *decode(const unsigned char *bytes, size_t length) {
    NSMutableData *out = [NSMutableData dataWithCapacity:length];
    static const unsigned char replacement[] = {0xEF, 0xBF, 0xBD};
    size_t i = 0;
    while (i < length) {
        unsigned char c = bytes[i];
        size_t need = c < 0x80 ? 1 : (c >= 0xC2 && c <= 0xDF) ? 2 : (c >= 0xE0 && c <= 0xEF) ? 3 : (c >= 0xF0 && c <= 0xF4) ? 4 : 0;
        BOOL valid = need > 0 && i + need <= length;
        for (size_t k = 1; valid && k < need; ++k) valid = (bytes[i + k] & 0xC0) == 0x80;
        if (valid && need == 3) valid = !(c == 0xE0 && bytes[i + 1] < 0xA0) && !(c == 0xED && bytes[i + 1] > 0x9F);
        if (valid && need == 4) valid = !(c == 0xF0 && bytes[i + 1] < 0x90) && !(c == 0xF4 && bytes[i + 1] > 0x8F);
        if (valid) { [out appendBytes:bytes + i length:need]; i += need; }
        else { [out appendBytes:replacement length:3]; i += 1; }
    }
    return minyar_native_copy_text(out.bytes, (long long)out.length);
}

static long long http_begin(const MinyarText *method, const MinyarText *url, const MinyarText *headers, const MinyarText *body,
                            NSURLCredential *credential, BOOL requiresIdentity) { @autoreleasepool {
    http_owner();
    if (!session) {
        NSURLSessionConfiguration *configuration = NSURLSessionConfiguration.defaultSessionConfiguration;
        configuration.timeoutIntervalForRequest = 60;
        // No local cache, as with the portable backend. CFNetwork otherwise
        // keeps every chunk of a response for the cache, joining the pieces
        // again for each chunk, so a long stream costs quadratic time.
        configuration.URLCache = nil;
        NSOperationQueue *queue = [NSOperationQueue new]; queue.maxConcurrentOperationCount = 1;
        session = [NSURLSession sessionWithConfiguration:configuration delegate:[MHDelegate new] delegateQueue:queue];
        requests = [NSMutableDictionary new];
        byTask = [NSMapTable strongToStrongObjectsMapTable];
    }
    NSString *verb = string(method);
    NSCharacterSet *token = [NSCharacterSet characterSetWithCharactersInString:@"ABCDEFGHIJKLMNOPQRSTUVWXYZ"];
    if (!verb.length || [verb rangeOfCharacterFromSet:token.invertedSet].location != NSNotFound)
        minyar_native_stop("http methods are uppercase words such as GET or POST.");
    NSURL *address = [NSURL URLWithString:string(url)];
    if (!address || !([address.scheme isEqualToString:@"https"] || [address.scheme isEqualToString:@"http"]) || !address.host.length)
        minyar_native_stop("http requests need an http:// or https:// URL.");
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:address];
    request.HTTPMethod = verb;
    request.mainDocumentURL = address;
    for (NSString *line in [string(headers) componentsSeparatedByString:@"\n"]) {
        if (!line.length) continue;
        NSRange colon = [line rangeOfString:@":"];
        if (colon.location == NSNotFound || colon.location == 0) minyar_native_stop("http headers are written \"Name: value\".");
        NSString *name = [line substringToIndex:colon.location];
        NSString *value = [[line substringFromIndex:colon.location + 1] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
        [request addValue:value forHTTPHeaderField:name];
    }
    if (body->byte_length) request.HTTPBody = [NSData dataWithBytes:body->bytes length:(NSUInteger)body->byte_length];
    if (nextRequest == LLONG_MAX) minyar_native_stop("http could not allocate a request.");
    MHRequest *r = [MHRequest new];
    r.unread = [NSMutableData new]; r.condition = [NSCondition new];
    long long handle = nextRequest++;
    requests[@(handle)] = r;
    if (requiresIdentity && (!credential || ![address.scheme isEqualToString:@"https"] || address.user || address.password)) {
        finish(r,@"an HTTPS request requires an accessible Keychain identity and valid intermediate certificates"); return handle;
    }
    r.clientCredential=credential; r.credentialOrigin=credential?address:nil;
    if (credential) {
        /* Client certificate credentials and authenticated pooled connections
         * must never be reused by an unrelated request or device identity. */
        NSURLSessionConfiguration *configuration=NSURLSessionConfiguration.ephemeralSessionConfiguration;
        configuration.timeoutIntervalForRequest=60; configuration.URLCache=nil;
        configuration.URLCredentialStorage=nil;
        NSOperationQueue *queue=[NSOperationQueue new]; queue.maxConcurrentOperationCount=1;
        r.identitySession=[NSURLSession sessionWithConfiguration:configuration delegate:[MHDelegate new] delegateQueue:queue];
    }
    r.task = [(r.identitySession?:session) dataTaskWithRequest:request];
    @synchronized(byTask) { [byTask setObject:r forKey:r.task]; }
    [r.task resume];
    return handle;
} }
long long minyar_http_begin(const MinyarText *method, const MinyarText *url, const MinyarText *headers, const MinyarText *body) {
    return http_begin(method,url,headers,body,nil,NO);
}
long long minyar_http_beginWithIdentity(const MinyarText *method, const MinyarText *url, const MinyarText *headers,
                                      const MinyarText *body, const MinyarBytes *reference, const MinyarBytes *chain) { @autoreleasepool {
    http_owner();
    return http_begin(method,url,headers,body,http_identity_credential(reference,chain),YES);
} }
bool minyar_http_wait(long long handle, double seconds) { @autoreleasepool {
    MHRequest *r = entry(handle);
    if (!isfinite(seconds) || seconds < 0 || seconds > 3600) minyar_native_stop("http waits must be between 0 and 3600 seconds.");
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:seconds];
    [r.condition lock];
    while (!r.done && [r.condition waitUntilDate:deadline]) {}
    BOOL done = r.done;
    [r.condition unlock];
    return done;
} }
bool minyar_http_finished(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    atomic_store(&wakePending, false);
    [r.condition lock]; BOOL done = r.done; [r.condition unlock];
    return done;
} }
long long minyar_http_status(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    [r.condition lock]; long long status = r.response.statusCode; [r.condition unlock];
    return status;
} }
MinyarText *minyar_http_reason(long long handle) { @autoreleasepool {
    long long status = minyar_http_status(handle);
    NSDictionary *phrases = @{@200: @"OK", @201: @"Created", @202: @"Accepted", @204: @"No Content",
        @301: @"Moved Permanently", @302: @"Found", @303: @"See Other", @304: @"Not Modified", @307: @"Temporary Redirect",
        @308: @"Permanent Redirect", @400: @"Bad Request", @401: @"Unauthorized", @403: @"Forbidden", @404: @"Not Found",
        @405: @"Method Not Allowed", @409: @"Conflict", @410: @"Gone", @413: @"Content Too Large", @415: @"Unsupported Media Type",
        @422: @"Unprocessable Content", @429: @"Too Many Requests", @500: @"Internal Server Error", @502: @"Bad Gateway",
        @503: @"Service Unavailable", @504: @"Gateway Timeout"};
    NSString *phrase = phrases[@(status)] ?: (status ? [NSHTTPURLResponse localizedStringForStatusCode:(NSInteger)status] : @"");
    return owned(phrase);
} }
MinyarText *minyar_http_header(long long handle, const MinyarText *name) { @autoreleasepool {
    MHRequest *r = entry(handle);
    [r.condition lock]; NSString *value = [r.response valueForHTTPHeaderField:string(name)]; [r.condition unlock];
    return owned(value);
} }
MinyarText *minyar_http_headerText(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    [r.condition lock]; NSDictionary *fields = r.response.allHeaderFields; [r.condition unlock];
    NSMutableArray *lines = [NSMutableArray new];
    for (NSString *name in [fields.allKeys sortedArrayUsingSelector:@selector(caseInsensitiveCompare:)])
        [lines addObject:[NSString stringWithFormat:@"%@: %@", name, fields[name]]];
    return owned([lines componentsJoinedByString:@"\n"]);
} }
MinyarText *minyar_http_read(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    atomic_store(&wakePending, false);
    [r.condition lock];
    const unsigned char *bytes = r.unread.bytes;
    // Hold back a character split between chunks until the rest arrives.
    size_t length = r.done ? r.unread.length : completeUTF8(bytes, r.unread.length);
    MinyarText *text = decode(bytes, length);
    [r.unread replaceBytesInRange:NSMakeRange(0, length) withBytes:NULL length:0];
    [r.condition unlock];
    return text;
} }
MinyarText *minyar_http_error(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    [r.condition lock]; NSString *error = r.error; [r.condition unlock];
    return owned(error);
} }
void minyar_http_cancel(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    [r.task cancel];
    finish(r, @"cancelled");
} }
void minyar_http_close(long long handle) { @autoreleasepool {
    MHRequest *r = entry(handle);
    [r.condition lock]; BOOL done=r.done; [r.condition unlock];
    if (!done) [r.task cancel];
    [requests removeObjectForKey:@(handle)];
} }
