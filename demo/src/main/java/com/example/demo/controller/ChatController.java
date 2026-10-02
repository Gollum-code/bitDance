package com.example.demo.controller;

import com.example.demo.auth.JwtPrincipal;
import com.example.demo.dto.ChatRequestDto;
import com.example.demo.dto.ChatResponseDto;
import com.example.demo.membership.MembershipService;
import com.example.demo.service.ChatService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatService chatService;
    private final MembershipService membershipService;

    public ChatController(ChatService chatService, MembershipService membershipService) {
        this.chatService = chatService;
        this.membershipService = membershipService;
    }

    private static String chatUserKey(JwtPrincipal principal) {
        return String.valueOf(principal.userId());
    }

    @PostMapping("/send")
    public ResponseEntity<Map<String, Object>> send(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String message
    ) {
        membershipService.assertAiAccess(principal.userId());
        String userId = chatUserKey(principal);
        try {
            String reply = chatService.chat(userId, message);
            String conversationId = chatService.getConversationId(userId);
            return ResponseEntity.ok(Map.of(
                    "success", true,
                    "reply", reply,
                    "conversationId", conversationId != null ? conversationId : ""
            ));
        } catch (Exception e) {
            return ResponseEntity.status(502).body(Map.of(
                    "success", false,
                    "reply", "",
                    "conversationId", "",
                    "error", e.getMessage() == null ? "chat failed" : e.getMessage()
            ));
        }
    }

    @PostMapping("/send-with-id")
    public ResponseEntity<ChatResponseDto> sendWithId(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestBody ChatRequestDto request
    ) {
        membershipService.assertAiAccess(principal.userId());
        try {
            String reply = chatService.chat(request.conversationId(), request.message());
            String conversationId = chatService.getConversationId(request.conversationId());
            return ResponseEntity.ok(new ChatResponseDto(
                    conversationId,
                    reply,
                    null,
                    null
            ));
        } catch (Exception e) {
            return ResponseEntity.status(502).body(new ChatResponseDto(
                    "",
                    "",
                    null,
                    Map.of("error", e.getMessage() == null ? "chat failed" : e.getMessage())
            ));
        }
    }

    @PostMapping("/new")
    public ResponseEntity<Map<String, Object>> newChat(
            @AuthenticationPrincipal JwtPrincipal principal,
            @RequestParam String message
    ) {
        membershipService.assertAiAccess(principal.userId());
        String userId = chatUserKey(principal);
        try {
            String reply = chatService.startNewChat(userId, message);
            String conversationId = chatService.getConversationId(userId);
            return ResponseEntity.ok(Map.of(
                    "success", true,
                    "reply", reply,
                    "conversationId", conversationId != null ? conversationId : ""
            ));
        } catch (Exception e) {
            return ResponseEntity.status(502).body(Map.of(
                    "success", false,
                    "reply", "",
                    "conversationId", "",
                    "error", e.getMessage() == null ? "new chat failed" : e.getMessage()
            ));
        }
    }

    @PostMapping("/clear")
    public ResponseEntity<Map<String, String>> clear(@AuthenticationPrincipal JwtPrincipal principal) {
        chatService.clearUserChat(chatUserKey(principal));
        return ResponseEntity.ok(Map.of(
                "success", "true",
                "message", "会话已清空"
        ));
    }

    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status(@AuthenticationPrincipal JwtPrincipal principal) {
        String userId = chatUserKey(principal);
        boolean active = chatService.hasActiveConversation(userId);
        String conversationId = chatService.getConversationId(userId);
        return ResponseEntity.ok(Map.of(
                "hasActiveConversation", active,
                "conversationId", conversationId != null ? conversationId : ""
        ));
    }
}
