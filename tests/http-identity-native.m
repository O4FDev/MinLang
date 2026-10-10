/* The real disposable Keychain fixture calls this while its identity exists. */
#include "../runtime/native/http.m"
#include <assert.h>
extern void minyar_rc_release(void *);

static MinyarText http_test_text(const char *value) {
    return (MinyarText){(const unsigned char *)value,(long long)strlen(value),-1,NULL,NULL};
}

static NSURLAuthenticationChallenge *http_challenge(NSString *host, NSInteger port,
                                                   NSString *protocol, NSString *method,
                                                   NSInteger failures) {
    NSURLProtectionSpace *space=[[NSURLProtectionSpace alloc] initWithHost:host port:port
        protocol:protocol realm:nil authenticationMethod:method];
    return [[NSURLAuthenticationChallenge alloc] initWithProtectionSpace:space proposedCredential:nil
        previousFailureCount:failures failureResponse:nil error:nil sender:(id)NSNull.null];
}
void minyar_test_http_identity(const MinyarBytes *reference) { @autoreleasepool {
    MinyarBytes empty={NULL,0,0,NULL,NULL};
    NSURLCredential *credential=http_identity_credential(reference,&empty);
    assert(credential.identity && !credential.certificates.count);
    /* Every truncation and every hostile length prefix fails closed. */
    for (long long size=0;size<reference->byte_length;size++) {
        MinyarBytes truncated=*reference; truncated.byte_length=size;
        assert(!http_identity_credential(&truncated,&empty));
    }
    for (unsigned n=1;n<=32;n++) {
        unsigned char wire[4]={(unsigned char)n,0,0,0};
        MinyarBytes bad={wire,4,0,NULL,NULL};
        assert(!http_identity_credential(reference,&bad));
    }
    MHRequest *r=[MHRequest new]; r.condition=[NSCondition new];
    r.clientCredential=credential; r.credentialOrigin=[NSURL URLWithString:@"https://device.example/"];
    NSURLAuthenticationChallenge *challenge=http_challenge(@"DEVICE.EXAMPLE",443,@"https",NSURLAuthenticationMethodClientCertificate,0);
    __block NSUInteger calls=0;
    http_authenticate(r,challenge,^(NSURLSessionAuthChallengeDisposition disposition,NSURLCredential *value) {
        calls++; assert(disposition==NSURLSessionAuthChallengeUseCredential && value==credential);
    });
    for (NSString *host in @[@"attacker.example",@"device.example.attacker.example"]) {
        challenge=http_challenge(host,443,@"https",NSURLAuthenticationMethodClientCertificate,0);
        http_authenticate(r,challenge,^(NSURLSessionAuthChallengeDisposition disposition,NSURLCredential *value) {
            calls++; assert(disposition==NSURLSessionAuthChallengeCancelAuthenticationChallenge && !value);
        });
    }
    for (unsigned mask=1;mask<8;mask++) {
        challenge=http_challenge(@"device.example",mask&1?8443:443,mask&2?@"http":@"https",
            NSURLAuthenticationMethodClientCertificate,mask&4?1:0);
        http_authenticate(r,challenge,^(NSURLSessionAuthChallengeDisposition disposition,NSURLCredential *value) {
            calls++; assert(disposition==NSURLSessionAuthChallengeCancelAuthenticationChallenge && !value);
        });
    }
    challenge=http_challenge(@"attacker.example",443,@"https",NSURLAuthenticationMethodServerTrust,0);
    http_authenticate(r,challenge,^(NSURLSessionAuthChallengeDisposition disposition,NSURLCredential *value) {
        calls++; assert(disposition==NSURLSessionAuthChallengePerformDefaultHandling && !value);
    });
    assert(calls==11);
    assert(http_same_origin(r.credentialOrigin,[NSURL URLWithString:@"https://DEVICE.EXAMPLE:443/path"]));
    assert(!http_same_origin(r.credentialOrigin,[NSURL URLWithString:@"http://device.example/path"]));
    assert(!http_same_origin(r.credentialOrigin,[NSURL URLWithString:@"https://device.example:8443/path"]));
    assert(!http_same_origin(r.credentialOrigin,[NSURL URLWithString:@"https://attacker.example/path"]));
    /* Completed/cancelled requests must not provide a certificate. */
    r.done=YES;
    challenge=http_challenge(@"device.example",443,@"https",NSURLAuthenticationMethodClientCertificate,0);
    http_authenticate(r,challenge,^(NSURLSessionAuthChallengeDisposition disposition,NSURLCredential *value) {
        assert(disposition==NSURLSessionAuthChallengeCancelAuthenticationChallenge && !value);
    });
    const char *url=getenv("MINYAR_TEST_OS_TLS_URL");
    if (url) {
        MinyarText method=http_test_text("GET"),address=http_test_text(url),blank=http_test_text("");
        long long handle=minyar_http_beginWithIdentity(&method,&address,&blank,&blank,reference,&empty);
        assert(minyar_http_wait(handle,10));
        MinyarText *error=minyar_http_error(handle);
        BOOL rejected=getenv("MINYAR_TEST_OS_TLS_REJECT")!=NULL;
        if (rejected) assert(minyar_http_status(handle)==0 && error->byte_length);
        else {
            if (error->byte_length) fprintf(stderr,"OS TLS failure: %.*s\n",(int)error->byte_length,error->bytes);
            assert(!error->byte_length && minyar_http_status(handle)==200);
            MinyarText *body=minyar_http_read(handle);
            assert(body->byte_length==2 && !memcmp(body->bytes,"ok",2)); minyar_rc_release(body);
        }
        minyar_rc_release(error); minyar_http_close(handle);
        if (!rejected) {
            MinyarText redirect=http_test_text(getenv("MINYAR_TEST_OS_TLS_REDIRECT"));
            handle=minyar_http_beginWithIdentity(&method,&redirect,&blank,&blank,reference,&empty);
            assert(minyar_http_wait(handle,10)); error=minyar_http_error(handle);
            assert(error->byte_length); minyar_rc_release(error); minyar_http_close(handle);
        }
    }
    puts("OS TLS client identity, default server trust and origin restrictions verified");
} }
